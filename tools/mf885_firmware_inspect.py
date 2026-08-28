#!/usr/bin/env python3
"""Inspect and compare MF885 ZIMI BackupFw/RestoreFw images without writing them.

The encrypted ZIMI header is device-bound.  Pass a read-only
``GetInfo&Id=Base`` XML response with ``--identity-xml`` to derive the key and
perform the complete structural verification.  The report never emits the
serial number, MAC address, derived AES key, or archive contents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


HEADER_SIZE = 0x23C
ENCRYPTED_HEADER_SIZE = 0x230
DESCRIPTOR_OFFSET = 0x68
DESCRIPTOR_SIZE = 0x1C
MAX_DESCRIPTORS = 16
CAFE_HEADER_SIZE = 20
CAFE_RECORD_HEADER_SIZE = 136
MAX_LZMA_UNCOMPRESSED_BYTES = 32 * 1024 * 1024
MAX_LZMA_MEMORY_BYTES = 64 * 1024 * 1024

OSLO_RUNTIME_BASE = 0x06000000
EXACT_OSLO_SIZE = 9_648_064
EXACT_OSLO_SHA256 = "d51fb378d8ccf68662174f39d6b8c4f6be5571280790bc3a4dc4a9e8a967078c"
FBF_WEBI_RECORD_STARTS = tuple(range(0x00C60000, 0x00AA0000, -0x20000))
FBF_FLASH_DENY_RANGES = {
    "GTL3/GWL3": (
        (0x00000000, 0x0001FFFF),
        (0x00060000, 0x0049FFFF),
        (0x004A0000, 0x0055FFFF),
    ),
    "GTL5/GWL5": (
        (0x00000000, 0x0001FFFF),
        (0x000A0000, 0x0093FFFF),
        (0x00940000, 0x00ABFFFF),
    ),
    "unknown-version-flag": ((0x00000000, 0x0001FFFF),),
}

# Exact-build signatures for the RestoreFw system-type prerequisite. Offsets are
# relative to the decompressed OSLO image whose runtime base is 0x06000000.
RESTOREFW_NATIVE_SIGNATURES = (
    ("system-type getter", 0x085A62, bytes.fromhex("42 48 08 38 00 78 70 47")),
    ("system-type storage literal", 0x085B6C, bytes.fromhex("08 12 00 06")),
    (
        "MINSYS predicate",
        0x0A0584,
        bytes.fromhex("10 b5 e5 f7 6c fa 04 28 01 d1 01 20 10 bd 00 20 10 bd"),
    ),
    ("MINSYS predicate veneer", 0x58DF54, bytes.fromhex("04 f0 1f e5 85 05 0a 06")),
    (
        "RestoreFw gate branch",
        0x6E84B8,
        bytes.fromhex("01 a8 65 f5 e2 ee a5 f6 4a ed 0a 4c 00 28 00 d1 38 e1 3f e1"),
    ),
    (
        "HTTP 500 rejection branch",
        0x6E873C,
        bytes.fromhex("ff 21 e2 68 f5 31 38 00 fd a3 fa f7 23 fd 9f e3"),
    ),
    ("RestoreFw rejection text", 0x6E8B3C, b"Not support the request\0"),
    ("GetSysType action", 0x6EBD0C, b"GetSysType\0"),
    (
        "GetSysType XML template",
        0x8AF39C,
        b'<?xml version="1.0" encoding="US-ASCII"?><RGW><sysinfo>'
        b"<systype>%s</systype></sysinfo></RGW>\0",
    ),
)

# Exact-build signatures for the stock FBF update path. These prove the parser,
# TPLIN-only missing-RSAI rejection, per-image XOR32 check, battery/pre-flash
# ordering and linked-list writer loop. They do not qualify a live upload.
FBF_UPDATE_NATIVE_SIGNATURES = (
    (
        "authenticated session gate entry",
        0x6E58D8,
        bytes.fromhex("ff b5 ed 49 18 1d 8f b0 0e 90 14 00 1d 00 4c c9"),
    ),
    (
        "xml_action and Upload route dispatch",
        0x6E5B38,
        bytes.fromhex(
            "b7 49 0f 98 1e f0 d0 ff 00 28 05 d1 0f 98 b5 a1 "
            "1e f0 ca ff 00 28 0e d0 68 69 00 28"
        ),
    ),
    (
        "TPLIN system-type predicate",
        0x0A05A8,
        bytes.fromhex("10 b5 e5 f7 5a fa 07 28 01 d1 01 20 10 bd 00 20 10 bd"),
    ),
    (
        "TPLIN-only missing-RSAI fatal branch",
        0x291128,
        bytes.fromhex(
            "0f f6 3e fa 00 28 12 d0 43 98 00 28 0f d1 7d 48 00 68 "
            "b0 42 05 d1 38 78 00 28 02 d0 ad a0 6f f1 17 f9 08 21 "
            "ba 48 81 60 02 24 e4 43 0e e3"
        ),
    ),
    (
        "FBF v11 and one-device parser gates",
        0x75C6D8,
        bytes.fromhex(
            "38 00 0c 00 20 30 41 78 00 78 0a 02 02 43 c4 48 0b 2a "
            "05 68 c3 48 06 78 0b d0 c3 48 85 42 05 d1 00 2e 03 d0 "
            "c1 a1 c4 a0 a3 f4 3a fe 10 20 07 b0 f0 bd 38 00 34 30 "
            "96 f0 74 ec 01 28 0b d0 ba 49 8d 42 06 d1 00 2e 04 d0 "
            "02 00 b8 a1 c3 a0 a3 f4 27 fe 11 20 eb e7 38 00 3c 30 "
            "96 f0 62 ec c7 19"
        ),
    ),
    (
        "FBF XOR32 checksum loop and compare",
        0x75C80C,
        bytes.fromhex(
            "02 00 00 20 53 18 01 e0 02 ca 48 40 9a 42 fb d3 70 47 "
            "f3 b5 04 00 81 b0 c1 f7 33 fc 00 90 21 68 02 98 ff f7 "
            "ed ff e1 68 70 4f 71 4e 05 00 81 42 21 d0"
        ),
    ),
    (
        "FBF version and hardware gate call",
        0x291156,
        bytes.fromhex("a5 48 ff f7 46 fc 00 28 0d d1"),
    ),
    (
        "FBF version and hardware gate wrapper",
        0x2909E8,
        bytes.fromhex(
            "7f b5 00 21 0a 00 0b 00 0d 00 6c 46 2e c4 69 46 "
            "ba f0 9e e9 00 28 1f d1 a3 4d a4 4c a4 4e 28 68 "
            "a0 42 07 d1 30 78 00 28 04 d0 6a 46 d9 a1 e1 a0 "
            "6f f1 ae fc 68 46 ba f0 90 e9 00 28 0c d0 28 68 "
            "a0 42 06 d1 30 78 00 28 03 d0 d2 a1 de a0 6f f1 "
            "9f fc 01 20 04 b0 70 bd"
        ),
    ),
    (
        "normal ZMIFI Upload path to FBF worker",
        0x2927A0,
        bytes.fromhex(
            "ba f0 52 eb fe f7 e5 f8 0d f6 ec fe 00 28 01 d1 "
            "fd f7 86 fd 00 21 64 20 b4 f1 eb f8 fd f7 b0 fd "
            "28 68 b0 42 05 d1 20 78"
        ),
    ),
    (
        "FBF 32M family and hardware-letter validation",
        0x719BB8,
        bytes.fromhex(
            "60 78 31 28 03 d1 43 f0 d6 f8 00 28 71 d1 60 78 "
            "32 28 03 d1 43 f0 cf f8 01 28 f7 d1 9a f6 9a eb"
        ),
    ),
    ("FBF header-version getter target", 0x34AD3C, struct.pack("<I", 0x0671D7A3)),
    ("FBF version validator target", 0x34AD44, struct.pack("<I", 0x06719959)),
    (
        "FBF record projection into native writer node",
        0x75C75C,
        bytes.fromhex(
            "34 20 70 43 c5 19 f4 35 28 00 14 30 96 f0 46 ec "
            "40 03 02 90 28 00 18 30 96 f0 40 ec 20 60 28 00 "
            "10 30 96 f0 3c ec 60 60 28 00 30 30 96 f0 36 ec "
            "e0 60 28 00 0c 30 96 f0 32 ec 60 61 02 98 a0 60 "
            "28 00 1c 30 96 f0 2a ec 20 61 28 00 96 f0 26 ec "
            "a0 61 28 00 96 f0 22 ec"
        ),
    ),
    (
        "battery gate then pre-flash and writer",
        0x2916DA,
        bytes.fromhex(
            "b9 f0 5e eb 00 28 10 d0 7e 48 01 68 75 48 81 42 05 d1 "
            "38 78 00 28 02 d0 a8 a0 6e f1 40 fe 03 20 28 60 04 20 "
            "34 00 a8 60 34 e7 b9 f0 4c eb 3c a8 fe f7 6f fe"
        ),
    ),
    ("battery gate target", 0x34AD9C, struct.pack("<I", 0x06719669)),
    ("pre-flash target", 0x34ADA4, struct.pack("<I", 0x06719DAD)),
    (
        "pre-flash then record-writer failure path",
        0x291704,
        bytes.fromhex(
            "b9 f0 4c eb 3c a8 fe f7 6f fe 00 28 10 d0 72 48 "
            "03 24 2c 60 01 68 68 48 81 42 05 d1 38 78 00 28 "
            "02 d0 a5 a0 6e f1 26 fe ac 60 04 24 e4 43 1c e7"
        ),
    ),
    (
        "pre-flash firmware entry",
        0x719DAC,
        bytes.fromhex(
            "f0 b5 8d b0 fd f7 93 ff 25 48 40 78 00 28 45 d1 "
            "24 4c 25 4d 20 68 a8 42 07 d1 50 48 00 78 00 28 "
            "03 d0 4f a1"
        ),
    ),
    ("pre-flash firmware function name", 0x719F0C, b"pre_flash_firmware\0"),
    (
        "native record validate and burn calls",
        0x29052C,
        bytes.fromhex(
            "9a 49 24 18 05 98 88 42 34 d0 03 99 28 00 ba f0 "
            "f2 eb 00 28 0e d0 5d 48 01 68 5d 48 81 42 06 d1 "
            "5c 48 00 78 00 28 02 d0 91 a0 6f f1 0f ff 00 20 "
            "c0 43 17 e0 04 99 20 00 02 f0 fe fb 03 99 28 00 "
            "ba f0 dc eb 00 28"
        ),
    ),
    ("native record validator target", 0x34AD24, struct.pack("<I", 0x0671E323)),
    ("native record burn target", 0x34AD2C, struct.pack("<I", 0x0675C909)),
    (
        "native erase-extent then write-stored-bytes routine",
        0x75C908,
        bytes.fromhex(
            "f3 b5 04 00 81 b0 c1 f7 be fb 65 69 06 00 01 00 "
            "28 00 f4 f4 a6 ea 00 29 01 d0 45 1c 75 43 00 20 "
            "5f f7 8f fc 20 69 00 22 29 00 5f f7 d8 fb 30 4e "
            "31 4f 05 00 10 d0 01 20 5f f7 83 fc 30 68 b8 42 "
            "08 d1 2c 48 00 78 00 28 04 d0 2a 00 7a a1 6c a0 "
            "a3 f4 0e fd 28 00 fe bd 22 68 20 69 02 99 00 23 "
            "5f f7 80 fb 04 00 10 d0 01 20 5f f7 6a fc 30 68 "
            "b8 42 08 d1 1f 48 00 78 00 28 04 d0 22 00 6e a1 "
            "66 a0 a3 f4 f5 fc 20 00 fe bd 01 20 5f f7 59 fc"
        ),
    ),
    (
        "generic flash start-address deny guard",
        0x6BBD3A,
        bytes.fromhex(
            "10 b5 04 00 6c f5 a9 f8 7c 49 09 78 00 29 01 d1 "
            "00 20 10 bd 01 68 a1 42 02 d8 41 68 a1 42 0b d2 "
            "81 68 a1 42 02 d8 c1 68 a1 42 05 d2 01 69 a1 42 "
            "12 d8 40 69 a0 42 0f d3 71 48 71 49 00 68 88 42 "
            "08 d1 70 48 00 78 00 28 04 d0 22 00 80 a1 84 a0 "
            "44 f5 f5 fa 33 20 10 bd 00 20 10 bd"
        ),
    ),
    ("erase wrapper flash-protect call", 0x6BBDAE, bytes.fromhex("ff f7 c4 ff")),
    ("write wrapper flash-protect call", 0x6BBE7E, bytes.fromhex("ff f7 5c ff")),
    (
        "flash deny-range initializer",
        0x427E9E,
        bytes.fromhex(
            "f8 b5 78 f4 4c fb 01 00 ff f7 f5 ff 04 00 fa 48 "
            "07 69 00 22 22 60 f9 4a 62 60 50 1c f9 4a 03 23 "
            "7f 26 5b 04 55 1c 76 04 72 29 7e d0 3c dc 68 29"
        ),
    ),
    (
        "supplied-record linked-list write loop",
        0x290F78,
        bytes.fromhex(
            "b4 42 00 da 55 e6 eb 4c eb 4e 20 68 b0 42 06 d1 ea 48 "
            "00 78 00 28 02 d0 f8 a0 6f f1 f1 f9 04 99 28 00 b9 f0 "
            "de ee 00 28 09 d1 20 68 b0 42 06 d1 e2 48 00 78 00 28 "
            "02 d0 fb a0 6f f1 e1 f9 20 68 b0 42 06 d1 dd 48 00 78 "
            "00 28 02 d0 fd a0 6f f1 d7 f9 ed 69 00 2d 00 d0"
        ),
    ),
    (
        "FBF body maximum-length gate",
        0x29106C,
        bytes.fromhex("52 98 13 22 af 4e b0 4f d2 04 90 42 0d dd"),
    ),
    (
        "previous OTA result zero-or-socket-error gate",
        0x6E9550,
        bytes.fromhex("2e f0 e0 fd 00 28 21 d0 07 28 1f d0"),
    ),
    (
        "previous OTA retry rejection diagnostics",
        0x6E97A4,
        b"[Error] previous OTA upload failed with code %d\0"
        b"[Error] should not handle OTA upload again, close socket\0",
    ),
    (
        "special minus-five MINS selector branch",
        0x292804,
        bytes.fromhex("7f 1d 02 d1 f3 49 f4 48 01 60 00 20 31 e0"),
    ),
    ("stock update worker call", 0x2927E2, bytes.fromhex("fe f7 04 fc")),
    (
        "successful update MAXS and reset-magic branch",
        0x29283E,
        bytes.fromhex("ef 49 e6 48 01 60 e5 49 ee 48 40 39 08 62"),
    ),
    (
        "successful update status finalizer",
        0x29284C,
        bytes.fromhex(
            "28 68 b0 42 05 d1 20 78 00 28 02 d0 ea a0 6d f1 "
            "8d fd 28 68 b0 42 05 d1 20 78 00 28 02 d0 ed a0 "
            "6d f1 84 fd 03 f0 93 f9 01 20 ba f0 f0 ea"
        ),
    ),
    ("successful update status finalizer target", 0x34CE5C, struct.pack("<I", 0x06719703)),
    (
        "successful update delayed reset",
        0x719938,
        bytes.fromhex(
            "d2 d1 05 e0 28 68 03 28 02 d1 68 46 43 f0 fa f9 "
            "4b 20 00 21 c0 00 2d f5 20 f8 46 f0 e7 ff 14 e5"
        ),
    ),
    ("OTA reset function name", 0x760B30, b"zimi_ota_reset\0"),
    ("MINS selector literal", 0x292BD8, bytes.fromhex("53 4e 49 4d")),
    ("retained selector address", 0x292BDC, bytes.fromhex("40 f0 d7 07")),
    ("MAXS selector literal", 0x292BFC, bytes.fromhex("53 58 41 4d")),
    ("upgrade reset magic", 0x292C00, bytes.fromhex("21 43 34 12")),
    ("upgrade failure cause zero", 0x7189BC, b"No Error!\0"),
    ("upgrade failure cause one", 0x7189C8, b"Image Size Error!\0"),
    ("upgrade failure cause two", 0x718A1C, b"Invalide Version!\0"),
    ("upgrade failure cause three", 0x718A30, b"Invalide Image!\0"),
    ("upgrade failure cause four", 0x718A40, b"Low Battry!\0"),
    ("upgrade failure cause five", 0x718A4C, b"IO Error!\0"),
    ("upgrade failure cause six", 0x718A58, b"Memory Error!\0"),
    ("upgrade failure cause seven", 0x718A68, b"Socket Error!\0"),
    ("upgrade failure cause default", 0x718A78, b"Unknown Error!\0"),
)

MINSYS_TRANSITION_NATIVE_SIGNATURES = (
    (
        "startup MINSYS recognition branch",
        0x0914C4,
        bytes.fromhex(
            "0f f0 5e f8 94 4d bc 4e bc 4c 00 28 08 d0 28 68 "
            "b0 42 05 d1 20 78 00 28 02 d0 c1 a0 6e f3 4a ff"
        ),
    ),
    (
        "normal-build minimum-system timer disabled guard",
        0x0F9138,
        bytes.fromhex("00 20 70 47"),
    ),
    (
        "minimum-system power-on timer early return",
        0x0FB82E,
        bytes.fromhex(
            "70 b5 05 00 fd f7 81 fc 00 28 1a d0 84 f1 28 e8 "
            "03 28 16 d0"
        ),
    ),
    (
        "retained MAXS/clear/MINS/reset-magic writers",
        0x29098E,
        bytes.fromhex(
            "ec 48 ec 49 08 60 70 47 eb 49 00 20 08 60 70 47 ea 48 "
            "e8 49 08 60 70 47 e7 49 e8 48 40 39 08 62 70 47 e4 49"
        ),
    ),
    (
        "early-phase MINS crash fallback",
        0x0937EC,
        bytes.fromhex("e3 48 00 68 06 28 02 d2 fd f1 d3 f8 0f e0 65 f0"),
    ),
    (
        "OTA MINS/MAXS/reset message dispatch",
        0x717AEC,
        bytes.fromhex(
            "01 2a 04 d0 02 2a 05 d0 03 2a 0d d1 09 e0 6f f6 92 ef "
            "01 e0 9c f6 f8 eb 7d 20 00 21"
        ),
    ),
    (
        "debugmode USB engineering-mode setter",
        0x266E04,
        bytes.fromhex(
            "00 b5 8b b0 28 21 01 a8 e7 f1 38 ea 08 20 42 f6 1c f9 "
            "00 28 01 d0 f5 a3"
        ),
    ),
    (
        "+LOG AT command registry",
        0x8EED70,
        bytes.fromhex(
            "01 00 00 00 8e c4 8d 06 f8 54 94 06 02 00 00 00 "
            "90 bc 8d 06 00 00 00 00 1d 4c 18 06 15 46 18 06"
        ),
    ),
    ("+LOG AT command name", 0x8DC48E, b"+LOG\0"),
    ("+LOG AT help text", 0x8DBC90, b"+LOG: (0: FLASH)\0"),
    (
        "+LOG numeric argument parsers and switch",
        0x184640,
        bytes.fromhex(
            "01 43 21 60 20 21 00 22 00 91 00 21 01 92 28 00 "
            "0b 00 10 aa b3 f0 a8 fb 01 28 73 d1 01 04 00 22 "
            "01 92 00 91 01 21 28 00 00 23 0f aa b3 f0 9c fb "
            "01 28 f2 d1 10 ab 1b 78 65 48 66 4f 01 25 c8 f2 "
            "76 eb"
        ),
    ),
    (
        "+LOG 33-case switch table",
        0x184682,
        bytes.fromhex(
            "21 25 12 16 25 1a 25 2e 35 3c 3f 25 25 25 25 4b "
            "f2 f1 f0 ef ee ed ec eb ea e9 e8 25 25 25 e7 e6 "
            "e5 b2 25"
        ),
    ),
    ("+LOG case-29 trampoline", 0x184850, bytes.fromhex("65 e1")),
    (
        "+LOG case-29 MINS write and watchdog call",
        0x184B1E,
        bytes.fromhex(
            "0f 99 71 48 00 29 02 d1 71 49 01 60 00 e0 06 60 "
            "06 f7 96 ff"
        ),
    ),
    (
        "+LOG case-29 selector literals",
        0x184CE8,
        bytes.fromhex("40 f0 d7 07 53 4e 49 4d"),
    ),
    (
        "hard watchdog-reset entry",
        0x08BA5E,
        bytes.fromhex(
            "70 b5 9a f3 7e eb 93 48 92 4a 41 68 08 00 80 30 "
            "c2 61 91 4b 03 62 4c 6e 64 08 64 00 4c 66 c2 61"
        ),
    ),
    (
        "engineering USB interface-4 receive callback",
        0x422D58,
        bytes.fromhex(
            "70 b5 eb 4d 0c 23 fe 4e ac 78 63 43 f0 50 98 19 "
            "81 60 42 60 64 1c 20 06 00 0e a8 70 e9 78 88 42"
        ),
    ),
    (
        "engineering USB AT worker queue message",
        0x422FD8,
        bytes.fromhex(
            "02 96 01 95 00 20 6b 46 18 70 90 48 0c 21 00 23 "
            "00 68 6a 46 eb f7 0a e9 00 28 0d d0"
        ),
    ),
    (
        "engineering USB interface-4 registration",
        0x4230DA,
        bytes.fromhex(
            "72 4a 00 21 0a 4e 01 92 00 91 2f 68 08 36 0a 00 "
            "04 21 30 78 00 23 b8 47 01 28 06 d0"
        ),
    ),
    (
        "AT channel queue initialization",
        0x095940,
        bytes.fromhex(
            "0c 22 58 48 00 92 10 22 1c 30 13 01 74 a1 85 f3 "
            "63 fd 00 28 06 d0 3f 4a 01 23 2b a1 b5 32 2e a0"
        ),
    ),
    (
        "AT channel CR-LF byte handling",
        0x095740,
        bytes.fromhex(
            "0a 28 22 d0 0d 28 20 d0 1a 28 12 d0 1b 28 18 d1"
        ),
    ),
    (
        "AT channel parser dispatch",
        0x095790,
        bytes.fromhex(
            "0d e0 00 98 c2 49 22 00 79 ac 80 00 08 58 21 00 "
            "b6 f1 3a ec 23 21 20 00 09 01 b8 f3 6a ed"
        ),
    ),
    (
        "AT parser ARM veneer",
        0x24C018,
        bytes.fromhex("04 f0 1f e5 9d d7 58 06"),
    ),
    (
        "AT or at line prefix parser",
        0x58D384,
        bytes.fromhex(
            "0c e0 20 28 09 d0 41 29 02 d1 54 28 0d d0 03 e0 "
            "61 29 01 d1 74 28 08 d0"
        ),
    ),
    (
        "AT equals-operation parser",
        0x58D504,
        bytes.fromhex(
            "3d 28 28 d1 60 78 64 1c 20 28 fb d0 20 78 3f 28 "
            "0b d1 60 78 64 1c 20 28 fb d0"
        ),
    ),
    (
        "hard watchdog-reset non-returning tail",
        0x08BAB4,
        bytes.fromhex(
            "01 22 12 04 00 20 40 1c 90 42 fc d3 88 6e c8 6e f8 e7"
        ),
    ),
    ("watchdog source marker", 0x08BCBC, b"watchdog.c\0"),
)

REGISTERED_AT_MINS_TRANSITION_BUILDS = {
    "2.5.89": {
        "size": 9_649_584,
        "sha256": "5ff94b1081427c87d984c83ecf6430834b2bee6ea97a81e291c17b614d565426",
        "registry_offset": 0x8EF364,
        "handler_offset": 0x1846D8,
        "argument_setup_offset": 0x184708,
        "numeric_parser_offset": 0x237E6C,
        "case_29_trampoline_offset": 0x184914,
        "case_29_block_offset": 0x184BE2,
        "selector_literals_offset": 0x184DAC,
        "watchdog_reset_address": "0x0608ba46",
        "watchdog_tail_offset": 0x08BA9C,
    },
    "2.5.94": {
        "size": EXACT_OSLO_SIZE,
        "sha256": EXACT_OSLO_SHA256,
        "registry_offset": 0x8EED74,
        "handler_offset": 0x184614,
        "argument_setup_offset": 0x184644,
        "numeric_parser_offset": 0x237DA8,
        "case_29_trampoline_offset": 0x184850,
        "case_29_block_offset": 0x184B1E,
        "selector_literals_offset": 0x184CE8,
        "watchdog_reset_address": "0x0608ba5e",
        "watchdog_tail_offset": 0x08BAB4,
    },
    "2.5.96": {
        "size": 9_648_128,
        "sha256": "4f69163a275f732605f41e7a57f78e247c15057c8410b0532a2a4f120015404d",
        "registry_offset": 0x8EEDB4,
        "handler_offset": 0x184614,
        "argument_setup_offset": 0x184644,
        "numeric_parser_offset": 0x237DA8,
        "case_29_trampoline_offset": 0x184850,
        "case_29_block_offset": 0x184B1E,
        "selector_literals_offset": 0x184CE8,
        "watchdog_reset_address": "0x0608ba5e",
        "watchdog_tail_offset": 0x08BAB4,
    },
}

EARLY_LOADER_HEADER_PREFIX = bytes.fromhex("04 00 00 06")
EARLY_LOADER_HEADER_SUFFIX = bytes.fromhex(
    "4c 4f 41 44 5f 54 41 42 "
    "4c 45 5f 53 49 47 4e 00 ad de d0 ba ad de d0 ba "
    "00 00 00 06 00 00 d8 07 45 45 45 45 00 f0 d4 07 "
    "fc ef d6 07 4f 42 4d 75 6e 6b 6e 00 ef ef ef ef"
)

EARLY_LOADER_ABI_BUILDS = {
    "2.5.89": {
        "size": 9_649_584,
        "sha256": "5ff94b1081427c87d984c83ecf6430834b2bee6ea97a81e291c17b614d565426",
        "header_pointer": 0x06933DB0,
        "function_offset": 0x142176,
        "name_offset": 0x1423C8,
        "literal_offset": 0x1423E0,
        "literal_refs": (0x1421A6, 0x142204),
    },
    "2.5.94": {
        "size": EXACT_OSLO_SIZE,
        "sha256": EXACT_OSLO_SHA256,
        "header_pointer": 0x069337C0,
        "function_offset": 0x1420B2,
        "name_offset": 0x142304,
        "literal_offset": 0x14231C,
        "literal_refs": (0x1420E2, 0x142140),
    },
    "2.5.96": {
        "size": 9_648_128,
        "sha256": "4f69163a275f732605f41e7a57f78e247c15057c8410b0532a2a4f120015404d",
        "header_pointer": 0x06933800,
        "function_offset": 0x1420B2,
        "name_offset": 0x142304,
        "literal_offset": 0x14231C,
        "literal_refs": (0x1420E2, 0x142140),
    },
}

USB_AT_DELIVERY_LINK_SIGNATURES = (
    ("interface-4 receive callback pointer", 0x4232A4, struct.pack("<I", 0x06422D59)),
    ("interface-4 endpoint map pointer", 0x423108, struct.pack("<I", 0x0695E444)),
    ("engineering USB worker pointer", 0x423248, struct.pack("<I", 0x06422F19)),
    ("engineering USB worker handle pointer", 0x42317C, struct.pack("<I", 0x06E8E310)),
    ("engineering USB worker AT queue pointer", 0x423224, struct.pack("<I", 0x06940CB4)),
    (
        "engineering USB worker route predicate call",
        0x422FCE,
        bytes.fromhex("00 20 5d f5 87 fd 01 28 15 d1"),
    ),
    ("AT queue initialization base pointer", 0x095AA4, struct.pack("<I", 0x06940C98)),
    ("AT task queue-base load", 0x0957AE, bytes.fromhex("bd 48")),
    ("AT task shared-queue load", 0x095624, bytes.fromhex("c0 69")),
    (
        "AT route initialization",
        0x095994,
        bytes.fromhex(
            "00 24 14 20 60 43 87 19 38 00 0c 30 ff f7 1f ff "
            "01 21 64 1c 0c 2c 79 74 f3 dd 62 4a 62 4b 00 20 "
            "15 54 19 54 40 1c 0c 28 fa db 39 48 41 62"
        ),
    ),
    ("AT channel task entry pointer", 0x095B28, struct.pack("<I", 0x0609560D)),
    (
        "AT channel task creation",
        0x095964,
        bytes.fromhex("70 49 00 22 70 a0 6b 46 07 c3 4d 48"),
    ),
    ("AT channel parser table pointer", 0x095AA0, struct.pack("<I", 0x06987048)),
    ("AT channel parser BLX", 0x0957A0, bytes.fromhex("b6 f1 3a ec")),
    ("AT parser veneer target", 0x24C01C, struct.pack("<I", 0x0658D79D)),
    ("first AT line-parser call", 0x58DA9E, bytes.fromhex("ff f7 42 fc")),
    ("second AT line-parser call", 0x58DD5E, bytes.fromhex("ff f7 e2 fa")),
    (
        "AT route table pointer",
        0x095B3C,
        struct.pack("<I", 0x06955408),
    ),
    ("AT route getter table pointer", 0x180EBC, struct.pack("<I", 0x06955408)),
    (
        "AT route getter",
        0x180AE2,
        bytes.fromhex("0c 28 02 d2 f5 49 08 5c 70 47 ff 20 70 47"),
    ),
    (
        "AT equals operation-2 dispatch",
        0x58D548,
        bytes.fromhex(
            "07 70 98 98 02 ab 82 18 00 92 96 98 02 21 8e aa ce e7"
        ),
    ),
    (
        "AT operation-2 common dispatcher call",
        0x58D4F0,
        bytes.fromhex("02 21 8e aa 96 98 00 23 fe f7 7c fd"),
    ),
    (
        "AT registry set-callback bridge",
        0x58CA68,
        bytes.fromhex(
            "39 78 fc 68 02 29 00 d0 03 20 c1 4b fd 69 92 9a "
            "6b 44 59 6e 23 00 a8 47 00 28"
        ),
    ),
)

# These links are part of the exact 2.5.94 MINS transition claim. Keeping them
# in the main signature set makes a broken pointer fail before semantic output.
MINSYS_TRANSITION_NATIVE_SIGNATURES += USB_AT_DELIVERY_LINK_SIGNATURES

AT_LOG_ARGUMENT_SETUP_SIGNATURE = bytes.fromhex(
    "20 21 00 22 00 91 00 21 01 92 28 00 0b 00 10 aa "
    "b3 f0 a8 fb 01 28 73 d1 01 04 00 22 01 92 00 91 "
    "01 21 28 00 00 23 0f aa b3 f0 9c fb 01 28 f2 d1"
)
AT_NUMERIC_PARSER_SIGNATURE = bytes.fromhex(
    "30 b5 c9 00 08 18 81 78 04 9d 03 9c 00 29 01 d0 "
    "15 60 07 e0 40 68 a0 42 01 dc 98 42 01 da 00 20 "
    "30 bd 10 60 01 20 30 bd"
)
WATCHDOG_NONRETURN_SIGNATURE = bytes.fromhex(
    "01 22 12 04 00 20 40 1c 90 42 fc d3 88 6e c8 6e f8 e7"
)

MINSYS_TRANSITION_NATIVE_SIGNATURES += (
    ("+LOG inclusive numeric parser", 0x237DA8, AT_NUMERIC_PARSER_SIGNATURE),
)

ENGINEERING_USB_NATIVE_SIGNATURES = (
    (
        "debugon model registry row",
        0x9007A0,
        bytes.fromhex(
            "5e 23 00 00 f2 e5 8d 06 01 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 05 6e 26 06 "
            "00 00 00 00 00 00 00 00"
        ),
    ),
    ("debugon model name", 0x8DE5F2, b"debugon\0"),
    (
        "debugon callback",
        0x266E04,
        bytes.fromhex(
            "00 b5 8b b0 28 21 01 a8 e7 f1 38 ea 08 20 42 f6 1c f9 "
            "00 28 01 d0 f5 a3 00 e0 f6 a3"
        ),
    ),
    ("debugon success result", 0x2671F0, b"success\0"),
    ("debugon failure result", 0x2671F8, b"failed\0"),
    ("debugon openmode leaf", 0x267200, b"openmode\0"),
    ("debugon callback root", 0x26720C, b"debugon\0"),
    (
        "debugmode USB mode-8 selector",
        0x0A904E,
        bytes.fromhex(
            "10 b5 01 00 fc f7 13 ff 04 00 20 78 88 42 0d d0 65 20 "
            "e0 70 08 00 c1 f1 a6 fd 20 78 08 28 01 d1 1e 20 a0 70 "
            "ff f7 7b ff 01 20 a8 e7 00 20 a6 e7"
        ),
    ),
    (
        "USB mode-to-descriptor switch",
        0x0A9312,
        bytes.fromhex(
            "28 78 74 4a 01 21 1e 26 03 28 1a d0 09 dc 00 28 0e d0 "
            "01 28 13 d0 02 28 17 d1 1f 20 60 70 11 70 14 e0 04 28 "
            "08 d0 10 28 0f d1 64 20 60 70 0d e0 1b 20 60 70 11 70 "
            "09 e0 1c 20 60 70 06 e0 66 70 04 e0 20 20 60 70 11 70 "
            "00 e0 66 70"
        ),
    ),
    (
        "descriptor-0x1e jump table",
        0x0A5EC0,
        bytes.fromhex(
            "02 24 11 00 19 39 02 91 04 21 1f 2a 01 d1 01 f0 18 fc "
            "0f dc 02 9b 06 2b 01 d3 02 f0 ef fd 5b 00 7b 44 9b 88 "
            "5b 00 9f 44 6b 00 0d 05 63 06 e7 08 e9 15 7f 0a"
        ),
    ),
    (
        "descriptor-0x1e device builder",
        0x0A73E8,
        bytes.fromhex(
            "12 23 01 27 ff 4a 13 70 57 70 95 70 d4 70 ef 23 13 71 "
            "54 71 97 71 40 23 d3 71 86 23 13 72 12 23 53 72 31 23 "
            "93 72 4e 23 d3 72 15 73 57 73 97 73 d4 73 03 23 13 74 "
            "57 74"
        ),
    ),
    (
        "engineering USB manufacturer string",
        0x92B3F0,
        bytes((0x10, 0x03)) + "Marvell".encode("utf-16le"),
    ),
    (
        "engineering USB mass-storage string",
        0x92B620,
        bytes((0x30, 0x03)) + "USB Mass Storage Device".encode("utf-16le"),
    ),
    (
        "engineering USB product string",
        0x92B650,
        bytes((0x38, 0x03)) + "Mobile Composite Device Bus".encode("utf-16le"),
    ),
    (
        "engineering USB compiled serial placeholder",
        0x92B688,
        bytes((0x26, 0x03)) + "200806006809080000".encode("utf-16le"),
    ),
    (
        "engineering USB AT string",
        0x92B6B0,
        bytes((0x28, 0x03)) + "Mobile AT Interface".encode("utf-16le"),
    ),
    (
        "engineering USB diagnostic string",
        0x92B6D8,
        bytes((0x2C, 0x03)) + "Mobile Diag Interface".encode("utf-16le"),
    ),
    (
        "engineering USB RNDIS string",
        0x92B708,
        bytes((0x3A, 0x03)) + "Mobile RNDIS Network Adapter".encode("utf-16le"),
    ),
)

ENGINEERING_USB_DEVICE_DESCRIPTOR = bytes.fromhex(
    "12 01 00 02 ef 02 01 40 86 12 31 4e 00 01 01 02 03 01"
)
ENGINEERING_USB_CONFIG_NO_STORAGE = bytes.fromhex(
    "09 02 79 00 04 01 00 c0 fa "
    "08 0b 00 02 e0 01 03 05 "
    "09 04 00 00 01 e0 01 03 05 "
    "05 24 00 10 01 05 24 01 00 01 04 24 02 00 05 24 06 00 01 "
    "07 05 8c 03 10 00 10 "
    "09 04 01 00 02 0a 00 00 05 "
    "07 05 8e 02 00 02 00 07 05 0d 02 00 02 00 "
    "09 04 02 00 02 ff 00 00 08 "
    "07 05 86 02 00 02 00 07 05 05 02 00 02 00 "
    "09 04 04 00 02 ff 00 00 0b "
    "07 05 83 02 00 02 00 07 05 02 02 00 02 00"
)
ENGINEERING_USB_CONFIG_WITH_STORAGE = ENGINEERING_USB_CONFIG_NO_STORAGE[:2] + bytes.fromhex(
    "90 00 05"
) + ENGINEERING_USB_CONFIG_NO_STORAGE[5:] + bytes.fromhex(
    "09 04 05 00 02 08 06 50 0d "
    "07 05 8b 02 00 02 00 07 05 0a 02 00 02 00"
)
ENGINEERING_USB_STRING_TABLE = {
    1: ("Marvell", "manufacturer"),
    2: ("Mobile Composite Device Bus", "product"),
    3: ("200806006809080000", "compiled-serial-placeholder"),
    5: ("Mobile RNDIS Network Adapter", "rndis"),
    8: ("Mobile Diag Interface", "diagnostic"),
    11: ("Mobile AT Interface", "at-command"),
    13: ("USB Mass Storage Device", "mass-storage"),
}

SYSTEM_TYPE_NAMES = {
    0: "MMIFI",
    1: "MIFI3",
    2: "MIFI4",
    3: "MIFI5",
    4: "MINSYS",
    5: "ZMIFI",
    7: "TPLIN",
}

KNOWN_ARTIFACTS = {
    "2b5880fc26805918bb574d07341ea9b863f8261be34c3bf9766fac0929204531": {
        "id": "mf885-2.5.94-golden",
        "size": 8_323_644,
        "role": "stock-golden",
        "structural_status": "verified",
        "restorable": True,
    },
    "f2ee088574634d822d5feed8210578a62788c8837fabc80129c6ce51ddfb429c": {
        "id": "mf885-community-0.0-canary-webui-r3",
        "size": 8_323_644,
        "role": "webui-canary",
        "structural_status": "quarantined-invalid-byte-sums",
        "restorable": False,
        "issue": "ZIMI global and WEBI additive byte sums do not match the unchanged encrypted header",
    },
    "65e5f5b507b9fcf49609a6fd1f010daa6f18111dc6a829d5655fa6bd30553517": {
        "id": "mf885-community-0.0-canary-logs-r1",
        "size": 8_323_644,
        "role": "webui-logs-canary",
        "structural_status": "quarantined-invalid-cafe-padding-live-confirmed",
        "restorable": False,
        "issue": "invalid CAFE padding metadata truncates three real JavaScript bytes at runtime; live test returned FULL with a syntax error and no canary panel",
    },
    "0cc9eb514d9a821a39b32d7c3f1b7b73f1358e3d79374bdd6b6c7340c308c1f1": {
        "id": "mf885-community-0.0-canary-logs-r2",
        "size": 8_323_644,
        "role": "webui-logs-canary",
        "structural_status": "quarantined-invalid-cafe-padding",
        "restorable": False,
        "issue": "invalid CAFE padding metadata would truncate three real JavaScript bytes; artifact was not flashed",
    },
    "f1f5f7fc51dc4bd6a094071cd82958b141f9525ba401bbf92024864e28f271a6": {
        "id": "mf885-community-0.0-sms-r1",
        "size": 8_323_644,
        "role": "webui-sms-canary",
        "structural_status": "quarantined-noncanonical-cafe-alignment",
        "restorable": False,
        "issue": "replacement CAFE records are not stored on the canonical four-byte boundary; artifact was not flashed",
    },
    "a9a284c5e5d2c8d0a18a55b0e324693b5a4a9f099eed814c3d20cd66a9cb642a": {
        "id": "mf885-community-0.0-canary-logs-r1-cafe2",
        "size": 8_323_644,
        "role": "webui-logs-canary",
        "structural_status": "quarantined-detailed-log-auth-omission-live-confirmed",
        "restorable": False,
        "issue": "CAFE container and panel were live-observed, but the canary detailed_log XHR omitted the stock Digest header; the empty HTTP 200 body did not verify native log content",
    },
    "444252fe98c231e2411c82656b1f03cd418e0ad0b4be3feafbc3ba2860270758": {
        "id": "mf885-community-0.0-canary-logs-r2-cafe2",
        "size": 8_323_644,
        "role": "webui-logs-canary",
        "structural_status": "quarantined-detailed-log-auth-omission",
        "restorable": False,
        "issue": "CAFE container is structurally verified, but the canary detailed_log XHR omits the stock Digest header; artifact was not flashed",
    },
    "de17be0290edb4d3192cf95d4dfca620550a0bf7a9adfbd3d22a15e5b14a518b": {
        "id": "mf885-community-0.0-canary-logs-r1-auth-r1-cafe2",
        "size": 8_323_644,
        "role": "webui-logs-canary",
        "structural_status": "quarantined-insufficient-diagnostic-redaction",
        "restorable": False,
        "issue": "authenticated source revision is structurally valid but can retain credentials and stable identifiers in copied diagnostics; artifact was not flashed",
    },
    "d18f87991caf7f8fe173da221d6317e47f9803c0e8b9c22fade4b8aa3ea6459f": {
        "id": "mf885-community-0.0-canary-logs-r2-auth-r1-cafe2",
        "size": 8_323_644,
        "role": "webui-logs-canary",
        "structural_status": "quarantined-insufficient-diagnostic-redaction",
        "restorable": False,
        "issue": "authenticated source revision is structurally valid but can retain credentials and stable identifiers in copied diagnostics; artifact was not flashed",
    },
    "fde992e34885b0d21167f8333758e577fc1b692430505f35791f3f75de0ec6af": {
        "id": "mf885-community-0.0-canary-logs-r1-auth-r2-prestorage-v1-cafe2",
        "size": 8_323_644,
        "role": "webui-logs-canary",
        "structural_status": "quarantined-incomplete-alternate-representation-redaction",
        "restorable": False,
        "issue": "authenticated source masks common values before storage, but alternate JSON and header spellings can survive diagnostic redaction; artifact was not flashed",
    },
    "5bfe13360711dc0204de8fdb690095fdcce4b0bb0b1160c58304d0d99f6d875c": {
        "id": "mf885-community-0.0-canary-logs-r2-auth-r2-prestorage-v1-cafe2",
        "size": 8_323_644,
        "role": "webui-logs-canary",
        "structural_status": "quarantined-incomplete-alternate-representation-redaction",
        "restorable": False,
        "issue": "bounded authenticated source masks common values before storage, but alternate JSON and header spellings can survive diagnostic redaction; artifact was not flashed",
    },
    "c77b66eb9ad817018c597b77d87caef9ab59ee3c14d2e2a6f134b9412dca7431": {
        "id": "mf885-community-0.0-canary-logs-r1-auth-r2-cafe2",
        "size": 8_323_644,
        "role": "webui-logs-canary",
        "structural_status": "quarantined-incomplete-wan-username-ipv6-redaction-live-confirmed",
        "restorable": False,
        "issue": "one exact device returned to FULL with the reviewed loader/script and an authenticated detailed_log XML read, but copied diagnostics did not cover every WAN username and IPv6 representation",
    },
    "1dc8f2e006b1ef32f0ffb99c358cc412e5e6b00fa676e024a81cf95a60b7bed1": {
        "id": "mf885-community-0.0-canary-logs-r2-auth-r2-cafe2",
        "size": 8_323_644,
        "role": "webui-logs-canary",
        "structural_status": "quarantined-incomplete-wan-username-ipv6-redaction",
        "restorable": False,
        "issue": "authenticated source revision is structurally verified and unflashed, but copied diagnostics do not cover every WAN username and IPv6 representation",
    },
    "8d5e9731615180ce09035ee969505fe6afe28d667143cfbed40030c580c5cd5d": {
        "id": "mf885-community-0.0-canary-logs-r1-auth-r3-cafe2",
        "size": 8_323_644,
        "role": "webui-logs-canary",
        "structural_status": "quarantined-incomplete-ipv6-redaction",
        "restorable": False,
        "issue": "source revision is structurally verified and unflashed, but its bare-IPv6 matcher is incomplete and can over-redact time-like values",
    },
    "ecb494b46875866dbe4274f5275cfef0a00607229291fdf96ebedcca56df6cf8": {
        "id": "mf885-community-0.0-canary-logs-r2-auth-r3-cafe2",
        "size": 8_323_644,
        "role": "webui-logs-canary",
        "structural_status": "quarantined-incomplete-ipv6-redaction",
        "restorable": False,
        "issue": "source revision is structurally verified and unflashed, but its bare-IPv6 matcher is incomplete and can over-redact time-like values",
    },
    "a1d970c68bde7534519b942bd73a57c6805d321860dead6b437392b0319fe922": {
        "id": "mf885-community-0.0-canary-logs-r1-auth-r4-cafe2",
        "size": 8_323_644,
        "role": "webui-logs-canary",
        "structural_status": "verified-not-flash-qualified",
        "restorable": False,
        "issue": "authenticated source with pre-storage WAN username and IPv6 masking is structurally verified and unflashed; rollback and live behavior remain unproved",
    },
    "aeaceb9cd193a44100bd33c3f14dc48ede6d2e163d7a214a87411d7875adf07f": {
        "id": "mf885-community-0.0-canary-logs-r2-auth-r4-cafe2",
        "size": 8_323_644,
        "role": "webui-logs-canary",
        "structural_status": "verified-not-flash-qualified",
        "restorable": False,
        "issue": "bounded authenticated source with pre-storage WAN username and IPv6 masking is structurally verified and unflashed; rollback and live behavior remain unproved",
    },
    "c27b5f7989ac4e4ac6ff1ebdd603685f6f1fe777918458059b620b1c36ec73ce": {
        "id": "mf885-community-0.0-sms-r1-cafe2",
        "size": 8_323_644,
        "role": "webui-sms-canary",
        "structural_status": "verified-not-flash-qualified",
        "restorable": False,
        "issue": "canonical CAFE container is structurally verified and unflashed; no delivery wrapper exists and rollback remains unproved",
    },
    "d42a912e31aafed4e57c6c98d94932444a0b2cf1fe0f8e223c95b3df22dae676": {
        "id": "mf885-community-0.1-community-r1-cafe2",
        "size": 8_323_644,
        "role": "webui-community",
        "structural_status": "verified-not-flash-qualified",
        "restorable": False,
        "issue": "golden-derived read/delete SMS profile was installed once and its exact static assets plus an authenticated empty inbox were observed; deletion and rollback remain unproved",
    },
    "aebc751d87d8a007fc50cfb6b0788a6168127ca8988d989176de902986a487ee": {
        "id": "mf885-community-0.2-community-r2-cafe2",
        "size": 8_323_644,
        "role": "webui-community",
        "structural_status": "verified-not-flash-qualified",
        "restorable": False,
        "issue": "golden-derived English-only Community R2 profile is reproducible and structurally verified, but it is unflashed and rollback remains unproved",
    },
    "51bd396c69e9c8db96249455092634b6b54552f64f5c4daee6f710b644759c95": {
        "id": "mf885-community-0.2.1-community-r2-cafe2",
        "size": 8_323_644,
        "role": "webui-community",
        "structural_status": "verified-not-flash-qualified",
        "restorable": False,
        "issue": "golden-derived Community R2.1 profile was installed once with its exact static assets observed after boot, but SMS mutations, cold boot, repeatability and rollback remain unproved and it is not flash-qualified",
    },
    "80e94750bf820e1fdbf6f51b8b2462cad633e28d19571610ce744bac7e6e04d5": {
        "id": "mf885-community-0.2.2-community-r2-cafe2",
        "size": 8_323_644,
        "role": "webui-community",
        "structural_status": "verified-not-flash-qualified",
        "restorable": False,
        "issue": "golden-derived Community R2.2 profile was installed once with its exact static assets and same-unit USB recovery observed after boot, but authenticated semantic UI, SMS mutations, cold boot, repeatability and rollback remain unproved and it is not flash-qualified",
    },
    "06d79b9e51d54e87e4065ceabac63d70b4d34b72b21bfa096a1132d1b45af86b": {
        "id": "mf885-community-0.2.3-community-r2-cafe2",
        "size": 8_323_644,
        "role": "webui-community",
        "structural_status": "verified-not-flash-qualified",
        "restorable": False,
        "issue": "golden-derived Community R2.3 profile is reproducible and structurally verified with offline desktop and mobile render review, but it is unflashed; live UI, SMS mutations, cold boot, repeatability and rollback remain unproved",
    },
    "5bc408710afa5e78836c49da91656a8f94d804ee4fe64c53f6ef7d53786fd7db": {
        "id": "mf885-community-0.2.4-community-r2-cafe2",
        "size": 8_323_644,
        "role": "webui-community",
        "structural_status": "verified-not-flash-qualified",
        "restorable": False,
        "issue": "golden-derived Community R2.4 profile is reproducible and structurally verified with a read-only modem monitor; it is unflashed and live UI, modem polling, SMS mutations, cold boot, repeatability and rollback remain unproved",
    },
}


class InspectionError(Exception):
    """Raised when an image cannot be parsed safely."""


@dataclass(frozen=True)
class IdentityMaterial:
    serial: bytes
    mac: bytes
    fingerprint: str
    key_fingerprint: str
    key: bytes


@dataclass(frozen=True)
class Partition:
    name: str
    checksum: int
    offset: int
    length: int


@dataclass(frozen=True)
class CafeRecord:
    path: str
    size: int
    sha256: str
    marker: int
    size_flags: int
    padding_bytes: int
    padding_valid: bool
    stored_size_aligned_4: bool
    logical_size: int | None
    logical_sha256: str | None


@dataclass
class ParsedImage:
    raw: bytes
    plaintext: bytes
    partitions: list[Partition]
    report: dict[str, Any]
    cafe_records: dict[str, list[CafeRecord]]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise InspectionError(f"u32 outside buffer at 0x{offset:x}")
    return struct.unpack_from("<I", data, offset)[0]


def byte_sum(data: bytes) -> int:
    return sum(data) & 0xFFFFFFFF


def hex32(value: int) -> str:
    return f"0x{value:08x}"


def safe_ascii(raw: bytes) -> str:
    raw = raw.split(b"\0", 1)[0]
    return "".join(chr(value) if 0x20 <= value <= 0x7E else f"\\x{value:02x}" for value in raw)


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def find_identity_value(root: ET.Element, names: set[str]) -> str:
    values = []
    for element in root.iter():
        if local_tag(element.tag) in names and element.text and element.text.strip():
            values.append(element.text.strip())
    unique = list(dict.fromkeys(values))
    if len(unique) != 1:
        raise InspectionError(f"identity XML must contain exactly one of {sorted(names)}")
    return unique[0]


def load_identity(path: Path) -> IdentityMaterial:
    try:
        root = ET.fromstring(path.read_bytes())
    except (OSError, ET.ParseError) as exc:
        raise InspectionError("identity XML could not be read or parsed") from exc

    serial_text = find_identity_value(root, {"sn", "serial", "serialnumber"})
    mac_text = find_identity_value(root, {"mac", "macaddress"})
    try:
        serial = serial_text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise InspectionError("identity serial is not ASCII") from exc
    if len(serial) != 15:
        raise InspectionError(f"identity serial must be exactly 15 ASCII bytes, got {len(serial)}")

    compact_mac = re.sub(r"[^0-9A-Fa-f]", "", mac_text)
    if len(compact_mac) != 12:
        raise InspectionError("identity MAC must contain exactly six bytes")
    try:
        mac = bytes.fromhex(compact_mac)
    except ValueError as exc:
        raise InspectionError("identity MAC is malformed") from exc

    mac_mix = (
        f"{mac[0]:02x}:{mac[1]:02x}:{mac[2]:02x}:{mac[3]:02x}:"
        f"{mac[4]:02x}{mac[5]:02x}"
    ).encode("ascii")
    serial_mix = serial + b"\0"
    base = b"0123456789abcdef"
    key = bytes(a ^ b ^ c for a, b, c in zip(base, mac_mix, serial_mix))
    identity_fingerprint = sha256(b"MF885-ZIMI-identity-v1\0" + serial + b"\0" + mac)
    return IdentityMaterial(
        serial=serial,
        mac=mac,
        fingerprint=identity_fingerprint,
        key_fingerprint=sha256(key),
        key=key,
    )


def decrypt_header(image: bytes, identity: IdentityMaterial) -> bytes:
    if len(image) < HEADER_SIZE:
        raise InspectionError(f"image is shorter than the 0x{HEADER_SIZE:x}-byte header")
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError as exc:
        raise InspectionError(
            "full header validation needs the Python 'cryptography' package"
        ) from exc
    decryptor = Cipher(algorithms.AES(identity.key), modes.CBC(bytes(16))).decryptor()
    plain_prefix = decryptor.update(image[:ENCRYPTED_HEADER_SIZE]) + decryptor.finalize()
    return plain_prefix + image[ENCRYPTED_HEADER_SIZE:HEADER_SIZE]


def parse_partitions(header: bytes, image_size: int) -> tuple[list[Partition], list[str]]:
    count = u32(header, 0x64)
    if count < 1 or count > MAX_DESCRIPTORS:
        raise InspectionError(f"invalid ZIMI partition count: {count}")
    partitions: list[Partition] = []
    errors: list[str] = []
    for index in range(count):
        base = DESCRIPTOR_OFFSET + index * DESCRIPTOR_SIZE
        if base + DESCRIPTOR_SIZE > len(header):
            raise InspectionError(f"partition descriptor {index} exceeds the header")
        name = safe_ascii(header[base : base + 4])
        checksum = u32(header, base + 0x10)
        offset = u32(header, base + 0x14)
        length = u32(header, base + 0x18)
        if not name:
            errors.append(f"descriptor {index} has an empty name")
        if offset < HEADER_SIZE or length == 0 or offset + length > image_size:
            errors.append(
                f"{name or index}: invalid range 0x{offset:x}+0x{length:x} for size 0x{image_size:x}"
            )
        partitions.append(Partition(name, checksum, offset, length))

    ordered = sorted(partitions, key=lambda part: part.offset)
    cursor = HEADER_SIZE
    for part in ordered:
        if part.offset != cursor:
            errors.append(
                f"layout is not contiguous before {part.name}: expected 0x{cursor:x}, got 0x{part.offset:x}"
            )
        cursor = part.offset + part.length
    if cursor != image_size:
        errors.append(f"layout ends at 0x{cursor:x}, image ends at 0x{image_size:x}")
    return partitions, errors


def inspect_restorefw_system_gate(unpacked: bytes) -> dict[str, Any]:
    """Report the exact-build RestoreFw prerequisite without probing a router.

    Native addresses are meaningful only for the reviewed 2.5.94 OSLO hash. An
    unknown or modified OSLO is therefore reported as unverified rather than
    being classified from coincidental strings or offsets.
    """

    digest = sha256(unpacked)
    exact_build_match = len(unpacked) == EXACT_OSLO_SIZE and digest == EXACT_OSLO_SHA256
    report: dict[str, Any] = {
        "schema": "mf885-native-restorefw-systype-gate/v1",
        "status": "unrecognized",
        "exact_build_match": exact_build_match,
        "oslo_bytes": len(unpacked),
        "oslo_sha256": digest,
        "required_oslo_bytes": EXACT_OSLO_SIZE,
        "required_oslo_sha256": EXACT_OSLO_SHA256,
    }
    if not exact_build_match:
        return report

    mismatches = [
        name
        for name, offset, expected in RESTOREFW_NATIVE_SIGNATURES
        if unpacked[offset : offset + len(expected)] != expected
    ]
    initial_value = unpacked[0x1200]
    expected_initial_table = bytes.fromhex(
        "05 5a 4d 49 46 49 00 00 04 4e 4f 4e 45 00 00 00 "
        "00 4d 4d 49 46 49 00 00 00 00 00 00 01 4d 49 46 "
        "49 33 00 00 00 00 00 00 02 4d 49 46 49 34 00 00 "
        "00 00 00 00 03 4d 49 46 49 35 00 00 00 00 00 00 "
        "04 4d 49 4e 53 59 53 00 00 00 00 00 05 5a 4d 49 "
        "46 49 00 00 00 00 00 00 07 54 50 4c 49 4e 00 00"
    )
    if unpacked[0x1200 : 0x1260] != expected_initial_table:
        mismatches.append("system-type initial value and enum table")

    if mismatches:
        report.update(
            {
                "status": "signature-mismatch",
                "native_signatures_valid": False,
                "signature_mismatches": mismatches,
            }
        )
        return report

    report.update(
        {
            "status": "verified",
            "native_signatures_valid": True,
            "signature_mismatches": [],
            "runtime_base": f"0x{OSLO_RUNTIME_BASE:08x}",
            "restorefw_handler_address": "0x066e8484",
            "system_type_getter_address": "0x06085a62",
            "system_type_predicate_address": "0x060a0584",
            "required_system_type": {"value": 4, "name": "MINSYS"},
            "compiled_initial_system_type": {
                "value": initial_value,
                "name": SYSTEM_TYPE_NAMES.get(initial_value, "UNKNOWN"),
            },
            "compiled_initial_value_satisfies_gate": initial_value == 4,
            "rejection_branch_address": "0x066e873c",
            "rejection_http_status": 500,
            "rejection_message": "Not support the request",
            "multipart_parser_entry_address": "0x066e874c",
            "rejection_precedes_multipart_and_firmware_bytes": True,
            "candidate_mode_diagnostic_action": "GetSysType",
            "candidate_mode_diagnostic_handler_purity_verified": False,
            "remote_mode_setter_identified_in_reviewed_static_analysis": False,
        }
    )
    return report


def inspect_fbf_update_path(unpacked: bytes) -> dict[str, Any]:
    """Report exact-build FBF gates without claiming upload qualification."""

    digest = sha256(unpacked)
    exact_build_match = len(unpacked) == EXACT_OSLO_SIZE and digest == EXACT_OSLO_SHA256
    report: dict[str, Any] = {
        "schema": "mf885-native-fbf-update-path/v4",
        "status": "unrecognized",
        "exact_build_match": exact_build_match,
        "oslo_bytes": len(unpacked),
        "oslo_sha256": digest,
    }
    if not exact_build_match:
        return report
    mismatches = [
        name
        for name, offset, expected in FBF_UPDATE_NATIVE_SIGNATURES
        if unpacked[offset : offset + len(expected)] != expected
    ]
    mismatches.extend(_fbf_update_link_mismatches(unpacked))
    if mismatches:
        report.update(
            {
                "status": "signature-mismatch",
                "native_signatures_valid": False,
                "signature_mismatches": mismatches,
            }
        )
        return report
    report.update(
        {
            "status": "verified",
            "native_signatures_valid": True,
            "signature_mismatches": [],
            "normal_system_type": {"value": 5, "name": "ZMIFI"},
            "authenticated_session_gate": True,
            "exact_auth_wire_mechanism_proven": False,
            "upload_action_dispatch_address": "0x062926e8",
            "normal_zmifi_upload_control_flow": True,
            "normal_zmifi_pre_update_address": "0x062902c0",
            "fbf_worker_address": "0x06290fee",
            "upload_command_query_key_recognized": True,
            "upload_command_value_required_proven": False,
            "missing_rsai_fatal_system_type": {"value": 7, "name": "TPLIN"},
            "missing_rsai_fatal_only_for_tplin": True,
            "zmifi_without_rsai_reaches_later_update_gates": True,
            "present_rsai_verification_required": True,
            "version_and_hardware_validation_precedes_write": True,
            "version_field_bytes": 12,
            "version_gate_semantics": {
                "32m_family_byte": "2",
                "candidate_hardware_letters_range": "version[6:11]",
                "reviewed_donor_version": "020589ABCD-2",
                "reviewed_target_hardware_suffix": "D",
                "reviewed_donor_passes_this_gate": True,
                "numeric_downgrade_compare_identified": False,
                "full_live_acceptance_proven": False,
            },
            "fbf_format_version": 11,
            "fbf_device_count": 1,
            "fbf_record_bytes": 0x34,
            "stored_payload_checksum": "xor32-little-endian-words",
            "writer_iterates_supplied_record_list": True,
            "fixed_full_partition_set_required_by_parser": False,
            "native_partition_whitelist_identified": False,
            "positive_partition_allowlist_identified": False,
            "generic_start_address_deny_guard": True,
            "flash_guard_checks_start_address_only": True,
            "full_extent_end_bound_check_identified": False,
            "flash_deny_ranges": {
                profile: [
                    {"start": f"0x{start:08x}", "end_inclusive": f"0x{end:08x}"}
                    for start, end in ranges
                ]
                for profile, ranges in FBF_FLASH_DENY_RANGES.items()
            },
            "candidate_webi_record_starts": [
                f"0x{address:08x}" for address in FBF_WEBI_RECORD_STARTS
            ],
            "candidate_webi_starts_pass_every_reviewed_guard_profile": all(
                not any(start <= address <= end for start, end in ranges)
                for address in FBF_WEBI_RECORD_STARTS
                for ranges in FBF_FLASH_DENY_RANGES.values()
            ),
            "native_record_write_order": "supplied-linked-record-order",
            "native_per_record_operation": "erase-full-extent-then-write-stored-bytes",
            "native_write_readback_identified": False,
            "native_readback_verified": False,
            "battery_gate_precedes_preflash_and_write": True,
            "pre_flash_firmware_address": "0x06719dac",
            "pre_flash_return_value_checked_by_worker": False,
            "cgi_route": "/xml_action.cgi?Action=Upload&file=upgrade&command=",
            "cgi_method": "POST",
            "content_length_required": True,
            "content_type_with_multipart_boundary_required": True,
            "maximum_content_length_bytes": 0x13 << 19,
            "upgrade_status_model": "upgrade_firmware",
            "upgrade_status_codes": {
                "0": "active-or-idle",
                "1": "success",
                "2": "active-or-processing",
                "3": "failure",
            },
            "upgrade_failure_causes": {
                "0": "No Error!",
                "1": "Image Size Error!",
                "2": "Invalide Version!",
                "3": "Invalide Image!",
                "4": "Low Battry!",
                "5": "IO Error!",
                "6": "Memory Error!",
                "7": "Socket Error!",
                "default": "Unknown Error!",
            },
            "native_new_upload_allowed_previous_causes": [0, 7],
            "native_socket_error_is_retryable": True,
            "success_retained_selector": {
                "value": "MAXS",
                "address": "0x07d7f040",
            },
            "success_reset_magic": {
                "value": "0x12344321",
                "address": "0x07d7f020",
            },
            "worker_minus_five_retained_selector": "MINS",
            "worker_minus_five_occurs_after_preflash_and_writer_attempt": True,
            "worker_minus_five_may_follow_partial_record_writes": True,
            "worker_minus_five_is_qualified_mins_entry": False,
            "success_status": 1,
            "success_delayed_reset_wait_units": 600,
            "success_reset_function": "zimi_ota_reset",
            "rollback_or_ab_fallback_identified": False,
            "rollback_verified": False,
            "webi_only_live_acceptance_proven": False,
            "flash_qualified": False,
        }
    )
    return report


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return value - (1 << bits) if value & sign else value


def _thumb_bl_target(unpacked: bytes, offset: int) -> int | None:
    first, second = struct.unpack_from("<HH", unpacked, offset)
    if first & 0xF800 != 0xF000 or second & 0xD000 != 0xD000:
        return None
    sign = (first >> 10) & 1
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    i1 = (~(j1 ^ sign)) & 1
    i2 = (~(j2 ^ sign)) & 1
    immediate = (
        (sign << 24)
        | (i1 << 23)
        | (i2 << 22)
        | ((first & 0x03FF) << 12)
        | ((second & 0x07FF) << 1)
    )
    return OSLO_RUNTIME_BASE + offset + 4 + _sign_extend(immediate, 25)


def _thumb_unconditional_branch_target(unpacked: bytes, offset: int) -> int | None:
    instruction = struct.unpack_from("<H", unpacked, offset)[0]
    if instruction & 0xF800 != 0xE000:
        return None
    immediate = _sign_extend((instruction & 0x07FF) << 1, 12)
    return OSLO_RUNTIME_BASE + offset + 4 + immediate


def _thumb_blx_target(unpacked: bytes, offset: int) -> int | None:
    first, second = struct.unpack_from("<HH", unpacked, offset)
    if first & 0xF800 != 0xF000 or second & 0xD001 != 0xC000:
        return None
    sign = (first >> 10) & 1
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    i1 = (~(j1 ^ sign)) & 1
    i2 = (~(j2 ^ sign)) & 1
    immediate = (
        (sign << 24)
        | (i1 << 23)
        | (i2 << 22)
        | ((first & 0x03FF) << 12)
        | (((second >> 1) & 0x03FF) << 2)
    )
    pc = (OSLO_RUNTIME_BASE + offset + 4) & ~3
    return pc + _sign_extend(immediate, 25)


def _thumb_adr_target(unpacked: bytes, offset: int) -> int | None:
    instruction = struct.unpack_from("<H", unpacked, offset)[0]
    if instruction & 0xF800 != 0xA000:
        return None
    pc = (OSLO_RUNTIME_BASE + offset + 4) & ~3
    return pc + (instruction & 0xFF) * 4


def _thumb_ldr_literal_address(unpacked: bytes, offset: int) -> int | None:
    instruction = struct.unpack_from("<H", unpacked, offset)[0]
    if instruction & 0xF800 != 0x4800:
        return None
    pc = (OSLO_RUNTIME_BASE + offset + 4) & ~3
    return pc + (instruction & 0xFF) * 4


def _fbf_update_link_mismatches(unpacked: bytes) -> list[str]:
    checks = (
        ("erase wrapper flash-protect call", _thumb_bl_target(unpacked, 0x6BBDAE), 0x066BBD3A),
        ("write wrapper flash-protect call", _thumb_bl_target(unpacked, 0x6BBE7E), 0x066BBD3A),
        ("FBF version gate wrapper call", _thumb_bl_target(unpacked, 0x291158), 0x062909E8),
        ("FBF header-version getter veneer", _thumb_blx_target(unpacked, 0x2909F8), 0x0634AD38),
        ("FBF version validator veneer", _thumb_blx_target(unpacked, 0x290A1E), 0x0634AD40),
        ("battery gate veneer", _thumb_blx_target(unpacked, 0x2916DA), 0x0634AD98),
        ("pre-flash veneer", _thumb_blx_target(unpacked, 0x291704), 0x0634ADA0),
        ("native record-writer call", _thumb_bl_target(unpacked, 0x29170A), 0x062903EC),
        ("native record validator veneer", _thumb_blx_target(unpacked, 0x29053A), 0x0634AD20),
        ("native record burn veneer", _thumb_blx_target(unpacked, 0x29056C), 0x0634AD28),
        ("stock update worker call", _thumb_bl_target(unpacked, 0x2927E2), 0x06290FEE),
        ("success follow-on call", _thumb_bl_target(unpacked, 0x292870), 0x06295B9A),
        ("success status finalizer veneer", _thumb_blx_target(unpacked, 0x292876), 0x0634CE58),
        ("success delay call", _thumb_bl_target(unpacked, 0x71994E), 0x06446992),
        ("success reset call", _thumb_bl_target(unpacked, 0x719952), 0x06760924),
        ("pre-flash name ADR", _thumb_adr_target(unpacked, 0x719DCE), 0x06719F0C),
    )
    mismatches = [name for name, actual, expected in checks if actual != expected]
    pointer_checks = (
        ("FBF header-version getter target", 0x34AD3C, 0x0671D7A3),
        ("FBF version validator target", 0x34AD44, 0x06719959),
        ("battery gate target", 0x34AD9C, 0x06719669),
        ("pre-flash target", 0x34ADA4, 0x06719DAD),
        ("native record validator target", 0x34AD24, 0x0671E323),
        ("native record burn target", 0x34AD2C, 0x0675C909),
        ("success status finalizer target", 0x34CE5C, 0x06719703),
    )
    for name, offset, expected in pointer_checks:
        if struct.unpack_from("<I", unpacked, offset)[0] != expected:
            mismatches.append(name)
    return mismatches


def inspect_early_loader_abi(unpacked: bytes) -> dict[str, Any]:
    """Report exact retained-page evidence without claiming a MINS consumer."""

    digest = sha256(unpacked)
    build_name = None
    profile = None
    for candidate, values in EARLY_LOADER_ABI_BUILDS.items():
        if len(unpacked) == values["size"] and digest == values["sha256"]:
            build_name = candidate
            profile = values
            break
    report: dict[str, Any] = {
        "schema": "mf885-early-loader-retained-page-abi/v1",
        "status": "unrecognized",
        "oslo_bytes": len(unpacked),
        "oslo_sha256": digest,
    }
    if profile is None or build_name is None:
        return report

    mismatches: list[str] = []
    if (
        unpacked[0x1C0:0x1C4] != EARLY_LOADER_HEADER_PREFIX
        or struct.unpack_from("<I", unpacked, 0x1C4)[0] != profile["header_pointer"]
        or unpacked[0x1C8:0x200] != EARLY_LOADER_HEADER_SUFFIX
    ):
        mismatches.append("OSLO load-table and OBM header")
    if unpacked[profile["function_offset"] : profile["function_offset"] + 2] != b"\xf0\xb5":
        mismatches.append("ReadBootloaderVersion function prologue")
    if unpacked[profile["name_offset"] : profile["name_offset"] + 22] != b"ReadBootloaderVersion\0":
        mismatches.append("ReadBootloaderVersion function name")
    if struct.unpack_from("<I", unpacked, profile["literal_offset"])[0] != 0x07D7F00C:
        mismatches.append("bootloader-version retained-page literal")
    expected_literal_address = OSLO_RUNTIME_BASE + profile["literal_offset"]
    resolved_refs = [
        _thumb_ldr_literal_address(unpacked, offset)
        for offset in profile["literal_refs"]
    ]
    if any(value != expected_literal_address for value in resolved_refs):
        mismatches.append("bootloader-version literal references")
    if mismatches:
        report.update(
            {
                "status": "signature-mismatch",
                "build": build_name,
                "native_signatures_valid": False,
                "signature_mismatches": mismatches,
            }
        )
        return report

    report.update(
        {
            "status": "verified",
            "build": build_name,
            "native_signatures_valid": True,
            "load_table_signature_offset": "0x000001c8",
            "obm_tag_offset": "0x000001f4",
            "bootloader_version_function_address": f"0x{OSLO_RUNTIME_BASE + profile['function_offset']:08x}",
            "bootloader_version_address": "0x07d7f00c",
            "bootloader_version_literal_offset": f"0x{profile['literal_offset']:08x}",
            "bootloader_version_literal_references": [
                f"0x{OSLO_RUNTIME_BASE + offset:08x}" for offset in profile["literal_refs"]
            ],
            "retained_page_base": "0x07d7f000",
            "mins_selector_address": "0x07d7f040",
            "bootloader_version_and_selector_addresses_share_page": True,
            "selector_consumer_analysis_performed": False,
            "selector_read_by_early_loader_proven": False,
        }
    )
    return report


def _usb_at_delivery_link_mismatches(unpacked: bytes) -> list[str]:
    mismatches = [
        name
        for name, offset, expected in USB_AT_DELIVERY_LINK_SIGNATURES
        if unpacked[offset : offset + len(expected)] != expected
    ]
    if struct.unpack_from("<I", unpacked, 0x095AA4)[0] + 0x1C != 0x06940CB4:
        mismatches.append("AT queue initialization does not resolve shared handle")
    if _thumb_bl_target(unpacked, 0x422FD0) != 0x06180AE2:
        mismatches.append("engineering USB worker route predicate")
    if _thumb_blx_target(unpacked, 0x0957A0) != 0x0624C018:
        mismatches.append("AT channel parser veneer call")
    if _thumb_bl_target(unpacked, 0x58D4F8) != 0x0658BFF4:
        mismatches.append("AT operation-2 dispatcher target")
    if _thumb_bl_target(unpacked, 0x58DA9E) != 0x0658D326:
        mismatches.append("first AT line-parser call")
    if _thumb_bl_target(unpacked, 0x58DD5E) != 0x0658D326:
        mismatches.append("second AT line-parser call")
    return mismatches


def inspect_registered_at_mins_transition(unpacked: bytes) -> dict[str, Any]:
    """Verify the registered +LOG case that writes MINS and hard-resets."""

    digest = sha256(unpacked)
    build_name = None
    profile = None
    if len(unpacked) == EXACT_OSLO_SIZE and digest == EXACT_OSLO_SHA256:
        build_name = "2.5.94"
        profile = REGISTERED_AT_MINS_TRANSITION_BUILDS[build_name]
    else:
        for candidate_name, candidate in REGISTERED_AT_MINS_TRANSITION_BUILDS.items():
            if candidate_name == "2.5.94":
                continue
            if len(unpacked) == candidate["size"] and digest == candidate["sha256"]:
                build_name = candidate_name
                profile = candidate
                break

    report: dict[str, Any] = {
        "schema": "mf885-registered-at-mins-transition/v2",
        "status": "unrecognized",
        "oslo_bytes": len(unpacked),
        "oslo_sha256": digest,
    }
    if profile is None or build_name is None:
        return report

    mismatches: list[str] = []
    registry_offset = profile["registry_offset"]
    registry = struct.unpack_from("<8I", unpacked, registry_offset)
    command_offset = registry[0] - OSLO_RUNTIME_BASE
    help_offset = registry[3] - OSLO_RUNTIME_BASE
    handler_offset = profile["handler_offset"]
    if unpacked[command_offset : command_offset + 5] != b"+LOG\0":
        mismatches.append("registered +LOG command name")
    if unpacked[help_offset : help_offset + 17] != b"+LOG: (0: FLASH)\0":
        mismatches.append("registered +LOG help text")
    if registry[2] != 2 or registry[4] != 0 or registry[6] != OSLO_RUNTIME_BASE + handler_offset + 1:
        mismatches.append("registered +LOG set-handler binding")
    if build_name == "2.5.94":
        mismatches.extend(_usb_at_delivery_link_mismatches(unpacked))
    argument_setup = profile["argument_setup_offset"]
    if unpacked[
        argument_setup : argument_setup + len(AT_LOG_ARGUMENT_SETUP_SIGNATURE)
    ] != AT_LOG_ARGUMENT_SETUP_SIGNATURE:
        mismatches.append("+LOG numeric argument setup")
    numeric_parser = profile["numeric_parser_offset"]
    if unpacked[
        numeric_parser : numeric_parser + len(AT_NUMERIC_PARSER_SIGNATURE)
    ] != AT_NUMERIC_PARSER_SIGNATURE:
        mismatches.append("+LOG inclusive numeric parser")

    table_limit_offset = handler_offset + 0x6E
    table_base = handler_offset + 0x6F
    if unpacked[table_limit_offset] != 33:
        mismatches.append("+LOG 33-case switch limit")
        case_29_trampoline = None
    else:
        case_29_trampoline = (table_base & ~1) + 2 * unpacked[table_base + 29]
        if case_29_trampoline != profile["case_29_trampoline_offset"]:
            mismatches.append("+LOG case-29 switch target")

    case_29_block = None
    if case_29_trampoline is not None:
        target = _thumb_unconditional_branch_target(unpacked, case_29_trampoline)
        case_29_block = target - OSLO_RUNTIME_BASE if target is not None else None
        if case_29_block != profile["case_29_block_offset"]:
            mismatches.append("+LOG case-29 trampoline")

    if case_29_block is not None:
        expected_prefix = bytes.fromhex(
            "0f 99 71 48 00 29 02 d1 71 49 01 60 00 e0 06 60"
        )
        if unpacked[case_29_block : case_29_block + 16] != expected_prefix:
            mismatches.append("+LOG MINS-or-clear selector write")
        watchdog = _thumb_bl_target(unpacked, case_29_block + 16)
        if watchdog != int(profile["watchdog_reset_address"], 16):
            mismatches.append("+LOG watchdog-reset target")
    selector_literals = profile["selector_literals_offset"]
    if unpacked[selector_literals : selector_literals + 8] != struct.pack(
        "<II", 0x07D7F040, 0x4D494E53
    ):
        mismatches.append("+LOG retained MINS selector literals")
    watchdog_tail = profile["watchdog_tail_offset"]
    if unpacked[
        watchdog_tail : watchdog_tail + len(WATCHDOG_NONRETURN_SIGNATURE)
    ] != WATCHDOG_NONRETURN_SIGNATURE:
        mismatches.append("watchdog non-returning tail")

    if mismatches:
        report.update(
            {
                "status": "signature-mismatch",
                "build": build_name,
                "signature_mismatches": mismatches,
            }
        )
        return report

    report.update(
        {
            "status": "verified",
            "build": build_name,
            "command_registry_record_address": (
                f"0x{OSLO_RUNTIME_BASE + registry_offset - 4:08x}"
            ),
            "command_name_field_address": (
                f"0x{OSLO_RUNTIME_BASE + registry_offset:08x}"
            ),
            "command_name": "+LOG",
            "declared_argument_count": 2,
            "set_handler_address": f"0x{OSLO_RUNTIME_BASE + handler_offset:08x}",
            "first_argument_range": {
                "minimum": 0,
                "maximum": 32,
                "local_storage_initialized_to": 0,
            },
            "second_argument_range": {
                "minimum": 0,
                "maximum": 65_536,
                "local_storage_initialized_to": 0,
            },
            "dispatch_case": 29,
            "second_argument_for_mins": 0,
            "nonzero_second_argument_clears_selector": True,
            "statically_derived_at_message": {
                "display": "AT+LOG=29,0<CR>",
                "hex": "41542b4c4f473d32392c300d",
            },
            "usb_at_channel_strips_terminator_bytes": ["0x0a", "0x0d"],
            "line_feed_transport_framing_proven": build_name == "2.5.94",
            "terminator_required_proven": False,
            "omitted_second_argument_accepted_by_external_parser_proven": False,
            "retained_selector_address": "0x07d7f040",
            "retained_selector_value": "MINS",
            "watchdog_reset_address": profile["watchdog_reset_address"],
            "watchdog_reset_returns": False,
            "final_ok_before_reset_expected": False,
            "registered_handler_to_mins_write_and_reset_proven": True,
            "static_usb_at_delivery_path_to_registry_proven": (
                build_name == "2.5.94"
            ),
            "external_usb_at_delivery_live_observed": False,
            "usb_at_delivery_chain": (
                {
                    "usb_mode": 8,
                    "interface": 4,
                    "bulk_out_endpoint": "0x02",
                    "receive_callback_address": "0x06422d58",
                    "worker_address": "0x06422f18",
                    "queue_handle_address": "0x06940cb4",
                    "channel_task_address": "0x0609560c",
                    "parser_address": "0x0658d79c",
                    "line_parser_address": "0x0658d326",
                    "equals_operation": 2,
                    "status": "verified-static",
                }
                if build_name == "2.5.94"
                else {"status": "not-reviewed-for-this-build"}
            ),
            "statically_resolvable_selector_reader_identified": False,
            "selector_reader_search_scope": (
                "reviewed exact normal OSLO/GRBI/RFBN artifacts"
            ),
            "selector_reader_search_complete": False,
            "post_reset_minsys_boot_observed": False,
            "safe_to_execute": False,
        }
    )
    return report


def inspect_minsys_transition_path(unpacked: bytes) -> dict[str, Any]:
    """Report the exact retained selector and unresolved MINS entry paths."""

    digest = sha256(unpacked)
    exact_build_match = len(unpacked) == EXACT_OSLO_SIZE and digest == EXACT_OSLO_SHA256
    report: dict[str, Any] = {
        "schema": "mf885-native-minsys-transition/v3",
        "status": "unrecognized",
        "exact_build_match": exact_build_match,
        "oslo_bytes": len(unpacked),
        "oslo_sha256": digest,
    }
    if not exact_build_match:
        return report
    mismatches = [
        name
        for name, offset, expected in MINSYS_TRANSITION_NATIVE_SIGNATURES
        if unpacked[offset : offset + len(expected)] != expected
    ]
    if mismatches:
        report.update(
            {
                "status": "signature-mismatch",
                "native_signatures_valid": False,
                "signature_mismatches": mismatches,
            }
        )
        return report
    registered_at_transition = inspect_registered_at_mins_transition(unpacked)
    report.update(
        {
            "status": "verified",
            "native_signatures_valid": True,
            "signature_mismatches": [],
            "retained_selector_address": "0x07d7f040",
            "selector_values": {
                "MINS": "0x4d494e53",
                "MAXS": "0x4d415853",
                "clear": "0x00000000",
            },
            "reset_magic_address": "0x07d7f020",
            "reset_magic_value": "0x12344321",
            "ota_message_actions": {"1": "MINS", "2": "MAXS", "3": "reset-only"},
            "proved_normal_image_ota_producers": [3],
            "early_phase_less_than": 6,
            "early_phase_fallback_writes_mins": True,
            "early_phase_path_kind": "fatal-exception-ee-log-handler",
            "startup_minsys_predicate_address": "0x060a0584",
            "startup_minsys_recognition_address": "0x060914c4",
            "startup_minsys_recognition_action": "log-current-system-type",
            "startup_minsys_recognition_is_entry_mechanism": False,
            "minimum_system_power_timer_address": "0x060fb82e",
            "minimum_system_power_timer_guard_address": "0x060f9138",
            "minimum_system_power_timer_guard_constant": 0,
            "minimum_system_power_timer_reachable_in_normal_build": False,
            "ordinary_power_cycle_runs_early_phase_handler_proven": False,
            "cold_power_cycle_preserves_retained_selector_proven": False,
            "physical_reset_key_to_fallback_timing_proven": False,
            "runtime_reset_isr_writes_selector": False,
            "debugmode_usb_mode": 8,
            "debugmode_writes_selector": False,
            "registered_at_mins_setter_handler_identified":
                registered_at_transition.get("status") == "verified",
            "registered_at_mins_transition": registered_at_transition,
            "reachable_remote_mins_setter_identified": False,
        }
    )
    return report


def _parse_usb_configuration_descriptor(blob: bytes, variant: str) -> dict[str, Any]:
    if len(blob) < 9 or blob[0:2] != b"\x09\x02":
        raise InspectionError("invalid USB configuration descriptor")
    total_length = struct.unpack_from("<H", blob, 2)[0]
    if total_length != len(blob):
        raise InspectionError("USB configuration total length mismatch")

    interfaces: list[dict[str, Any]] = []
    associations: list[dict[str, Any]] = []
    current_interface: dict[str, Any] | None = None
    position = 0
    transfer_types = {0: "control", 1: "isochronous", 2: "bulk", 3: "interrupt"}
    while position < len(blob):
        descriptor_length = blob[position]
        if descriptor_length < 2 or position + descriptor_length > len(blob):
            raise InspectionError("truncated USB descriptor")
        descriptor_type = blob[position + 1]
        descriptor = blob[position : position + descriptor_length]
        if descriptor_type == 0x0B and descriptor_length == 8:
            associations.append(
                {
                    "first_interface": descriptor[2],
                    "interface_count": descriptor[3],
                    "class": descriptor[4],
                    "subclass": descriptor[5],
                    "protocol": descriptor[6],
                    "string_index": descriptor[7],
                }
            )
        elif descriptor_type == 0x04 and descriptor_length == 9:
            current_interface = {
                "number": descriptor[2],
                "alternate_setting": descriptor[3],
                "declared_endpoint_count": descriptor[4],
                "class": descriptor[5],
                "subclass": descriptor[6],
                "protocol": descriptor[7],
                "string_index": descriptor[8],
                "endpoints": [],
            }
            interfaces.append(current_interface)
        elif descriptor_type == 0x05 and descriptor_length == 7:
            if current_interface is None:
                raise InspectionError("USB endpoint precedes interface")
            attributes = descriptor[3]
            current_interface["endpoints"].append(
                {
                    "address": descriptor[2],
                    "direction": "in" if descriptor[2] & 0x80 else "out",
                    "transfer_type": transfer_types[attributes & 0x03],
                    "max_packet_bytes": struct.unpack_from("<H", descriptor, 4)[0],
                    "interval": descriptor[6],
                }
            )
        position += descriptor_length

    unique_interfaces = {item["number"] for item in interfaces}
    if len(unique_interfaces) != blob[4]:
        raise InspectionError("USB interface count mismatch")
    for item in interfaces:
        if len(item["endpoints"]) != item["declared_endpoint_count"]:
            raise InspectionError("USB endpoint count mismatch")

    role_hints = {
        0: ("rndis-control", "descriptor-proven"),
        1: ("rndis-data", "descriptor-proven"),
        2: ("diagnostic", "native-string-registration-proven"),
        4: ("at-command", "native-string-registration-proven"),
        5: ("mass-storage", "descriptor-proven"),
    }
    for item in interfaces:
        role, confidence = role_hints.get(
            item["number"], ("unknown", "not-identified")
        )
        item["role"] = role
        item["role_confidence"] = confidence

    return {
        "variant": variant,
        "total_length": total_length,
        "declared_interface_count": blob[4],
        "configuration_value": blob[5],
        "attributes": blob[7],
        "maximum_power_ma": blob[8] * 2,
        "interface_associations": associations,
        "interfaces": interfaces,
    }


def inspect_engineering_usb_profile(unpacked: bytes) -> dict[str, Any]:
    """Report the exact normal-mode USB profile selected by debugmodeon."""

    digest = sha256(unpacked)
    exact_build_match = len(unpacked) == EXACT_OSLO_SIZE and digest == EXACT_OSLO_SHA256
    report: dict[str, Any] = {
        "schema": "mf885-native-engineering-usb-profile/v1",
        "status": "unrecognized",
        "exact_build_match": exact_build_match,
        "oslo_bytes": len(unpacked),
        "oslo_sha256": digest,
    }
    if not exact_build_match:
        return report
    mismatches = [
        name
        for name, offset, expected in ENGINEERING_USB_NATIVE_SIGNATURES
        if unpacked[offset : offset + len(expected)] != expected
    ]
    if mismatches:
        report.update(
            {
                "status": "signature-mismatch",
                "native_signatures_valid": False,
                "signature_mismatches": mismatches,
            }
        )
        return report

    device = ENGINEERING_USB_DEVICE_DESCRIPTOR
    configurations = [
        _parse_usb_configuration_descriptor(
            ENGINEERING_USB_CONFIG_NO_STORAGE, "mass-storage-disabled"
        ),
        _parse_usb_configuration_descriptor(
            ENGINEERING_USB_CONFIG_WITH_STORAGE, "mass-storage-enabled"
        ),
    ]
    report.update(
        {
            "status": "verified",
            "native_signatures_valid": True,
            "signature_mismatches": [],
            "trigger_model": "debugmodeon/debugon",
            "usb_mode": 8,
            "descriptor_selector": "0x1e",
            "model_registry": {
                "row_address": "0x069007a0",
                "name": "debugon",
                "callback_phase": "post_get",
                "callback_pair_offset": "0x28",
                "callback_pointer_slot_offset": "0x2c",
                "callback_pointer_raw": "0x06266e05",
                "callback_code_address": "0x06266e04",
                "other_callback_slots_null": True,
            },
            "callback_semantics": {
                "requested_usb_mode": 8,
                "result_literals": ["success", "failed"],
                "empty_openmode_is_activation": False,
                "external_activation_request_proven": False,
                "external_off_callback_identified": False,
            },
            "system_type_change": False,
            "retained_mins_selector_written": False,
            "device": {
                "usb_version_bcd": f"0x{struct.unpack_from('<H', device, 2)[0]:04x}",
                "class": device[4],
                "subclass": device[5],
                "protocol": device[6],
                "endpoint_zero_max_packet_bytes": device[7],
                "vendor_id": f"0x{struct.unpack_from('<H', device, 8)[0]:04x}",
                "product_id": f"0x{struct.unpack_from('<H', device, 10)[0]:04x}",
                "device_version_bcd": f"0x{struct.unpack_from('<H', device, 12)[0]:04x}",
                "manufacturer_string_index": device[14],
                "product_string_index": device[15],
                "serial_string_index": device[16],
                "configuration_count": device[17],
            },
            "configurations": configurations,
            "string_descriptors": [
                {
                    "index": index,
                    "text": text,
                    "role": role,
                    "runtime_override_possible": role == "compiled-serial-placeholder",
                }
                for index, (text, role) in ENGINEERING_USB_STRING_TABLE.items()
            ],
            "engineering_descriptor_interfaces_present_in_image": True,
            "service_loader_protocol_identified": False,
            "service_interface_to_mins_transition_proven": False,
            "safe_live_activation_recommended": False,
        }
    )
    return report


def inspect_lzma(payload: bytes, partition_name: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"format": "lzma-alone"}
    try:
        decoder = lzma.LZMADecompressor(
            format=lzma.FORMAT_ALONE, memlimit=MAX_LZMA_MEMORY_BYTES
        )
        unpacked = decoder.decompress(payload, max_length=MAX_LZMA_UNCOMPRESSED_BYTES + 1)
        if len(unpacked) > MAX_LZMA_UNCOMPRESSED_BYTES:
            result.update(
                {
                    "stream_complete": False,
                    "error": "uncompressed-size-limit",
                    "uncompressed_limit_bytes": MAX_LZMA_UNCOMPRESSED_BYTES,
                }
            )
            return result
        consumed = len(payload) - len(decoder.unused_data)
        padding = decoder.unused_data
        result.update(
            {
                "stream_complete": decoder.eof,
                "compressed_bytes": consumed,
                "uncompressed_bytes": len(unpacked),
                "uncompressed_sha256": sha256(unpacked),
                "padding_bytes": len(padding),
                "padding_all_ff": bool(padding) and all(value == 0xFF for value in padding),
            }
        )
        if partition_name == "OSLO" and decoder.eof:
            result["restorefw_system_gate"] = inspect_restorefw_system_gate(unpacked)
            result["fbf_update_path"] = inspect_fbf_update_path(unpacked)
            result["minsys_transition_path"] = inspect_minsys_transition_path(unpacked)
            result["early_loader_abi"] = inspect_early_loader_abi(unpacked)
            result["engineering_usb_profile"] = inspect_engineering_usb_profile(unpacked)
    except lzma.LZMAError as exc:
        result.update({"stream_complete": False, "error": type(exc).__name__})
    return result


def parse_cafe(payload: bytes, include_records: bool) -> tuple[dict[str, Any], list[CafeRecord]]:
    if len(payload) < CAFE_HEADER_SIZE or u32(payload, 0) != 0xCAFECAFE:
        raise InspectionError("partition does not start with a CAFE archive")
    stored_adler = u32(payload, 4)
    format_word = u32(payload, 8)
    reserved = [u32(payload, 12), u32(payload, 16)]
    position = CAFE_HEADER_SIZE
    records: list[CafeRecord] = []
    seen_paths: set[str] = set()
    duplicate_paths: list[str] = []
    while True:
        if position + 4 > len(payload):
            raise InspectionError("CAFE archive has no DADADADA sentinel")
        marker = u32(payload, position)
        if marker == 0xDADADADA:
            sentinel_offset = position
            break
        if marker >> 16 != 0xCAFE:
            raise InspectionError(f"invalid CAFE record marker 0x{marker:08x} at 0x{position:x}")
        if position + CAFE_RECORD_HEADER_SIZE > len(payload):
            raise InspectionError("truncated CAFE record header")
        size_flags = u32(payload, position + 4)
        size = size_flags & 0x00FFFFFF
        padding_bytes = size_flags >> 24
        path_text = safe_ascii(payload[position + 8 : position + CAFE_RECORD_HEADER_SIZE])
        data_start = position + CAFE_RECORD_HEADER_SIZE
        data_end = data_start + size
        if not path_text or data_end > len(payload):
            raise InspectionError(f"invalid CAFE record at 0x{position:x}")
        stored_data = payload[data_start:data_end]
        logical_size = size - padding_bytes if padding_bytes <= size else None
        logical_data = stored_data[:logical_size] if logical_size is not None else None
        padding_valid = (
            padding_bytes <= 3
            and logical_size is not None
            and (padding_bytes == 0 or stored_data[-padding_bytes:] == b"\xFF" * padding_bytes)
        )
        if path_text in seen_paths:
            duplicate_paths.append(path_text)
        seen_paths.add(path_text)
        records.append(
            CafeRecord(
                path=path_text,
                size=size,
                sha256=sha256(payload[data_start:data_end]),
                marker=marker,
                size_flags=size_flags,
                padding_bytes=padding_bytes,
                padding_valid=padding_valid,
                stored_size_aligned_4=size % 4 == 0,
                logical_size=logical_size,
                logical_sha256=sha256(logical_data) if logical_data is not None else None,
            )
        )
        position = data_end

    computed_adler = zlib.adler32(payload[8:sentinel_offset]) & 0xFFFFFFFF
    padding = payload[sentinel_offset + 4 :]
    listing = [
        {
            "path": record.path,
            "size": record.size,
            "sha256": record.sha256,
            "marker": hex32(record.marker),
            "size_flags": hex32(record.size_flags),
            "padding_bytes": record.padding_bytes,
            "padding_valid": record.padding_valid,
            "stored_size_aligned_4": record.stored_size_aligned_4,
            "logical_size": record.logical_size,
            "logical_sha256": record.logical_sha256,
        }
        for record in records
    ]
    invalid_padding_paths = [record.path for record in records if not record.padding_valid]
    unaligned_stored_paths = [record.path for record in records if not record.stored_size_aligned_4]
    report: dict[str, Any] = {
        "format": "cafe",
        "format_word": hex32(format_word),
        "reserved_words": [hex32(value) for value in reserved],
        "record_count": len(records),
        "sentinel_offset": f"0x{sentinel_offset:x}",
        "stored_adler32": hex32(stored_adler),
        "computed_adler32": hex32(computed_adler),
        "adler32_valid": stored_adler == computed_adler,
        "duplicate_paths": duplicate_paths,
        "record_padding_valid": not invalid_padding_paths,
        "invalid_padding_paths": invalid_padding_paths,
        "stored_sizes_aligned_4": not unaligned_stored_paths,
        "unaligned_stored_paths": unaligned_stored_paths,
        "padding_bytes": len(padding),
        "padding_all_ff": bool(padding) and all(value == 0xFF for value in padding),
        "record_manifest_sha256": sha256(
            "\n".join(f"{r.path}\0{r.size}\0{r.sha256}" for r in records).encode("utf-8")
        ),
        "logical_record_manifest_sha256": sha256(
            "\n".join(
                f"{r.path}\0{r.logical_size}\0{r.logical_sha256}\0{r.padding_bytes}"
                for r in records
            ).encode("utf-8")
        ),
    }
    if include_records:
        report["records"] = listing
    return report, records


def artifact_info(name: str, data: bytes) -> dict[str, Any]:
    digest = sha256(data)
    known = KNOWN_ARTIFACTS.get(digest)
    return {
        "name": name,
        "size": len(data),
        "sha256": digest,
        "known_artifact": dict(known) if known else None,
        "known_size_valid": bool(known and known["size"] == len(data)),
    }


def known_is_quarantined(artifact: dict[str, Any]) -> bool:
    known = artifact.get("known_artifact")
    return bool(known and str(known.get("structural_status", "")).startswith("quarantined-"))


def inspect_image(path: Path, identity: IdentityMaterial | None, include_records: bool) -> ParsedImage:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InspectionError(f"could not read image {path.name!r}") from exc
    artifact = artifact_info(path.name, raw)
    report: dict[str, Any] = {
        "schema": "mf885-zimi-inspection/v1",
        "artifact": artifact,
        "identity": None,
        "header": {"state": "encrypted-not-inspected"},
        "partitions": [],
        "verification": {
            "status": (
                "invalid"
                if known_is_quarantined(artifact)
                else "known-exact"
                if artifact["known_size_valid"]
                else "incomplete"
            ),
            "structurally_verified": False,
            "errors": (
                [artifact["known_artifact"]["issue"]]
                if known_is_quarantined(artifact)
                else []
            ),
        },
    }
    if identity is None:
        return ParsedImage(raw, b"", [], report, {})

    header = decrypt_header(raw, identity)
    plaintext = header + raw[HEADER_SIZE:]
    partitions, layout_errors = parse_partitions(header, len(raw))
    stored_global = u32(header, 0x1C)
    computed_global = byte_sum(plaintext[0x20:])
    header_report: dict[str, Any] = {
        "state": "decrypted",
        "plaintext_sha256": sha256(header),
        "magic": safe_ascii(header[0:4]),
        "description": safe_ascii(header[0x04:0x1C]),
        "stored_global_byte_sum": hex32(stored_global),
        "computed_global_byte_sum": hex32(computed_global),
        "global_byte_sum_valid": stored_global == computed_global,
        "format_version": u32(header, 0x20),
        "software": safe_ascii(header[0x24:0x44]),
        "hardware": safe_ascii(header[0x44:0x64]),
        "partition_count": u32(header, 0x64),
        "encrypted_prefix_bytes": ENCRYPTED_HEADER_SIZE,
        "plaintext_tail_bytes": HEADER_SIZE - ENCRYPTED_HEADER_SIZE,
    }
    report["identity"] = {
        "source": "GetInfo/Base XML",
        "identity_fingerprint_sha256": identity.fingerprint,
        "derived_key_sha256": identity.key_fingerprint,
        "serial_or_mac_disclosed": False,
    }
    report["header"] = header_report

    errors = list(layout_errors)
    if header[0:4] != b"ZIMI":
        errors.append("decrypted header magic is not ZIMI")
    if stored_global != computed_global:
        errors.append("global additive byte checksum mismatch")

    cafe_records: dict[str, list[CafeRecord]] = {}
    partition_reports = []
    for partition in partitions:
        payload = raw[partition.offset : partition.offset + partition.length]
        computed = byte_sum(payload)
        item: dict[str, Any] = {
            "name": partition.name,
            "offset": f"0x{partition.offset:x}",
            "length": f"0x{partition.length:x}",
            "stored_byte_sum": hex32(partition.checksum),
            "computed_byte_sum": hex32(computed),
            "byte_sum_valid": partition.checksum == computed,
            "sha256": sha256(payload),
        }
        if partition.checksum != computed:
            errors.append(f"{partition.name}: additive byte checksum mismatch")
        if partition.name in {"OSLO", "GRBI", "RFBN"}:
            item["payload"] = inspect_lzma(payload, partition.name)
            if not item["payload"].get("stream_complete"):
                errors.append(f"{partition.name}: LZMA stream did not complete")
        elif payload[:4] == struct.pack("<I", 0xCAFECAFE):
            try:
                cafe_report, records = parse_cafe(payload, include_records)
                item["payload"] = cafe_report
                cafe_records[partition.name] = records
                if not cafe_report["adler32_valid"]:
                    errors.append(f"{partition.name}: CAFE Adler-32 mismatch")
                if cafe_report["duplicate_paths"]:
                    errors.append(f"{partition.name}: duplicate CAFE paths")
                if not cafe_report["record_padding_valid"]:
                    errors.append(
                        f"{partition.name}: invalid CAFE record padding: "
                        + ", ".join(cafe_report["invalid_padding_paths"])
                    )
                if not cafe_report["stored_sizes_aligned_4"]:
                    errors.append(
                        f"{partition.name}: noncanonical CAFE stored-size alignment: "
                        + ", ".join(cafe_report["unaligned_stored_paths"])
                    )
            except InspectionError as exc:
                item["payload"] = {"format": "cafe", "error": str(exc)}
                errors.append(f"{partition.name}: {exc}")
        else:
            item["payload"] = {"format": "opaque"}
        partition_reports.append(item)

    report["partitions"] = partition_reports
    if known_is_quarantined(artifact) and artifact["known_artifact"]["issue"] not in errors:
        errors.append(artifact["known_artifact"]["issue"])
    report["verification"] = {
        "status": "verified" if not errors else "invalid",
        "structurally_verified": not errors,
        "errors": errors,
    }
    return ParsedImage(raw, plaintext, partitions, report, cafe_records)


def diff_ranges(left: bytes, right: bytes) -> tuple[int, list[dict[str, Any]]]:
    ranges: list[dict[str, Any]] = []
    total = 0
    run_start: int | None = None
    common = min(len(left), len(right))
    for index in range(common):
        different = left[index] != right[index]
        if different:
            total += 1
            if run_start is None:
                run_start = index
        elif run_start is not None:
            ranges.append(
                {"start": f"0x{run_start:x}", "end": f"0x{index - 1:x}", "bytes": index - run_start}
            )
            run_start = None
    if run_start is not None:
        ranges.append(
            {"start": f"0x{run_start:x}", "end": f"0x{common - 1:x}", "bytes": common - run_start}
        )
    if len(left) != len(right):
        ranges.append(
            {
                "start": f"0x{common:x}",
                "end": f"0x{max(len(left), len(right)) - 1:x}",
                "bytes": abs(len(left) - len(right)),
                "reason": "length-difference",
            }
        )
        total += abs(len(left) - len(right))
    return total, ranges


def compare_cafe(left: Iterable[CafeRecord], right: Iterable[CafeRecord]) -> dict[str, Any]:
    left_map = {record.path: record for record in left}
    right_map = {record.path: record for record in right}
    changed = []
    for path in sorted(left_map.keys() & right_map.keys()):
        before = left_map[path]
        after = right_map[path]
        if (before.size, before.sha256, before.marker, before.size_flags) != (
            after.size,
            after.sha256,
            after.marker,
            after.size_flags,
        ):
            changed.append(
                {
                    "path": path,
                    "size_before": before.size,
                    "size_after": after.size,
                    "sha256_before": before.sha256,
                    "sha256_after": after.sha256,
                }
            )
    return {
        "added_paths": sorted(right_map.keys() - left_map.keys()),
        "removed_paths": sorted(left_map.keys() - right_map.keys()),
        "changed_records": changed,
    }


def compare_images(left: ParsedImage, right: ParsedImage) -> dict[str, Any]:
    raw_count, raw_ranges = diff_ranges(left.raw, right.raw)
    report: dict[str, Any] = {
        "left": {
            "name": left.report["artifact"]["name"],
            "sha256": left.report["artifact"]["sha256"],
            "verification": left.report["verification"]["status"],
        },
        "right": {
            "name": right.report["artifact"]["name"],
            "sha256": right.report["artifact"]["sha256"],
            "verification": right.report["verification"]["status"],
            "errors": right.report["verification"]["errors"],
        },
        "raw_diff_bytes": raw_count,
        "raw_diff_ranges": raw_ranges,
        "same_size": len(left.raw) == len(right.raw),
        "encrypted_header_byte_identical": left.raw[:HEADER_SIZE] == right.raw[:HEADER_SIZE],
        "partitions": [],
        "cafe": {},
    }
    if left.partitions and right.partitions:
        right_by_name = {part.name: part for part in right.partitions}
        for part in left.partitions:
            other = right_by_name.get(part.name)
            if other is None:
                report["partitions"].append({"name": part.name, "present_in_both": False})
                continue
            left_payload = left.raw[part.offset : part.offset + part.length]
            right_payload = right.raw[other.offset : other.offset + other.length]
            count, ranges = diff_ranges(left_payload, right_payload)
            report["partitions"].append(
                {
                    "name": part.name,
                    "present_in_both": True,
                    "same_offset": part.offset == other.offset,
                    "same_length": part.length == other.length,
                    "byte_identical": count == 0,
                    "diff_bytes": count,
                    "diff_ranges_partition_relative": ranges,
                }
            )
        for name in sorted(left.cafe_records.keys() | right.cafe_records.keys()):
            report["cafe"][name] = compare_cafe(
                left.cafe_records.get(name, []), right.cafe_records.get(name, [])
            )
    return report


def print_text(report: dict[str, Any], comparison: dict[str, Any] | None) -> None:
    artifact = report["artifact"]
    known = artifact["known_artifact"]
    print(f"Artifact: {artifact['name']}")
    print(f"Size: {artifact['size']} bytes")
    print(f"SHA-256: {artifact['sha256']}")
    print(f"Known: {known['id']} ({known['role']})" if known else "Known: no")
    print(f"Verification: {report['verification']['status']}")
    header = report["header"]
    if header["state"] == "decrypted":
        print(
            f"ZIMI: {header['software']} / {header['hardware']} / "
            f"global-sum={'OK' if header['global_byte_sum_valid'] else 'FAIL'}"
        )
        identity = report["identity"]
        print(f"Identity fingerprint: {identity['identity_fingerprint_sha256']}")
        print(f"Derived-key fingerprint: {identity['derived_key_sha256']}")
        for part in report["partitions"]:
            payload = part["payload"]
            detail = payload["format"]
            if detail == "cafe":
                detail += f" records={payload.get('record_count', '?')} adler={'OK' if payload.get('adler32_valid') else 'FAIL'}"
            elif detail == "lzma-alone":
                detail += f" out={payload.get('uncompressed_bytes', '?')}"
                gate = payload.get("restorefw_system_gate")
                if gate and gate.get("status") == "verified":
                    required = gate["required_system_type"]["name"]
                    initial = gate["compiled_initial_system_type"]["name"]
                    detail += f" restorefw={required}-only compiled-default={initial}"
                fbf_path = payload.get("fbf_update_path")
                if fbf_path and fbf_path.get("status") == "verified":
                    detail += " fbf=ZMIFI-no-RSAI-passes-presence-gate-only"
                minsys = payload.get("minsys_transition_path")
                if minsys and minsys.get("status") == "verified":
                    detail += " AT-MINS-handler=static-candidate"
                usb = payload.get("engineering_usb_profile")
                if usb and usb.get("status") == "verified":
                    detail += " usb-debug=1286:4e31-RNDIS+DIAG+AT-not-MINS"
            print(
                f"  {part['name']:4} {part['offset']}+{part['length']} "
                f"sum={'OK' if part['byte_sum_valid'] else 'FAIL'} {detail}"
            )
    else:
        print("ZIMI header: encrypted; pass --identity-xml for structural verification")
    for error in report["verification"]["errors"]:
        print(f"ERROR: {error}")
    if comparison is not None:
        print(
            f"Comparison: {comparison['right']['name']} is "
            f"{comparison['right']['verification']}; {comparison['raw_diff_bytes']} differing raw bytes"
        )
        for error in comparison["right"]["errors"]:
            print(f"COMPARE ERROR: {error}")
        print(f"Encrypted header identical: {comparison['encrypted_header_byte_identical']}")
        for part in comparison["partitions"]:
            if part.get("present_in_both"):
                print(f"  {part['name']:4} diff-bytes={part['diff_bytes']}")
        for name, cafe in comparison["cafe"].items():
            paths = [item["path"] for item in cafe["changed_records"]]
            if paths or cafe["added_paths"] or cafe["removed_paths"]:
                print(f"  {name} changed records: {', '.join(paths) or '(membership only)'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only structural inspector for MF885 ZIMI BackupFw/RestoreFw images"
    )
    parser.add_argument("image", type=Path, help="firmware image to inspect")
    parser.add_argument(
        "--identity-xml",
        type=Path,
        help="read-only GetInfo&Id=Base XML used to derive the device-bound header key",
    )
    parser.add_argument("--compare", type=Path, help="second image for a byte/logical comparison")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--list-records",
        action="store_true",
        help="include CAFE record paths, sizes and hashes (never contents)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        identity = load_identity(args.identity_xml) if args.identity_xml else None
        primary = inspect_image(args.image, identity, args.list_records)
        comparison = None
        secondary = None
        if args.compare:
            secondary = inspect_image(args.compare, identity, args.list_records)
            comparison = compare_images(primary, secondary)
        if args.json:
            output: dict[str, Any] = {"image": primary.report}
            if secondary is not None:
                output["compared_image"] = secondary.report
                output["comparison"] = comparison
            print(json.dumps(output, indent=2, sort_keys=True))
        else:
            print_text(primary.report, comparison)

        statuses = [primary.report["verification"]["status"]]
        if secondary is not None:
            statuses.append(secondary.report["verification"]["status"])
        if "invalid" in statuses:
            return 2
        if "incomplete" in statuses:
            return 3
        return 0
    except InspectionError as exc:
        print(f"inspection failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
