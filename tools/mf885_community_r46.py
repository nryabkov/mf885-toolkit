#!/usr/bin/env python3
"""Pinned R4.6 assets with native-state TTL editing; no device I/O."""
from pathlib import Path
import mf885_community_r2 as r2
import mf885_community_r45 as previous
PROFILE='0.4.6-community-r2'
MARKER=b'MF885 Community R4.6 extension 0.4.6-community-r2'
ENTRY_PATH='www\\r46.html'
APP_PATH='www\\js\\r46app.js'
CSS_PATH='www\\css\\r46ui.css'
TTL_APP_PATH='www\\js\\r46ttl.js'
TTL_CSS_PATH='www\\css\\r46ttl.css'
REMOVED_RECORDS=previous.REMOVED_RECORDS
REMOVED_ARCHIVE_BYTES=previous.REMOVED_ARCHIVE_BYTES
OUTPUT_RECORDS={'www\\help_en.html': (21381,
                       '00f8097d158c9bbe9dc28af72d4ce1ea8bd940ca42f0669e51c779a4d6eef7b2'),
 'www\\html\\adminApp.html': (4766,
                              'aefdbebd7a7ab183e95151425f1563298a57fa6136b9cc3003cb536054197b67'),
 'www\\index.html': (26636,
                     'df2fd9d3dd55504bd38b7ce45f50aa02d798dc6e8ac7bdaf6193173e3ba77e88'),
 'www\\js\\base\\ajax_calls.js': (21467,
                                  'f8f2326f9d32a55d3566a9b5b743ae0fcd979c4d755ffec3823086b44068c127'),
 'www\\js\\base\\utils.js': (16873,
                             '5aa5c57d1e194c9ce0d21e946ad4b2358cd754d15c7bfb570bdef327d6c64103'),
 'www\\properties\\Messages_en.properties': (46943,
                                             '2c602877a1d515a8b022136ba289ef887a1eeffba27d13d761403146dc93d60c')}
ADDITION_OUTPUT_RECORDS={'www\\css\\r46ttl.css': (945,
                          'dbd3ecf613a198281af74a30d402a591f2766e12e31e35bc1550c9a67fc4d3a1',
                          'R4.6 native state editor; hardware qualification '
                          'pending'),
 'www\\css\\r46ui.css': (7925,
                         '50b977ba920c226a4a9c03895c47d1457439adba0eefd169c20e2cca21244578',
                         'R4.6 native state editor; hardware qualification '
                         'pending'),
 'www\\js\\r46app.js': (65240,
                        '06b1477544cc65746974db272f553caab36c50bd74d2f445eeaa28d0bbf4ef8f',
                        'R4.6 native state editor; hardware qualification '
                        'pending'),
 'www\\js\\r46ttl.js': (8813,
                        '114db9d334020dd1ecb0b26c5c6482eb92164e63211ebec4fae3e10efac4c530',
                        'R4.6 native state editor; hardware qualification '
                        'pending'),
 'www\\r46.html': (16924,
                   '98e09013988203160fc8b04e7f048d1e1248ef146f9de1af5e9899e3cda7bec5',
                   'R4.6 native state editor; hardware qualification pending')}
class CommunityR46Error(RuntimeError):pass

def _revise(raw):
    for old,new in ((b'0.4.5',b'0.4.6'),(b'R4.5',b'R4.6'),(b'r45',b'r46'),(b'R45',b'R46')):raw=raw.replace(old,new)
    return raw

def assets(root):
    base=root/('public/webui/r4.6' if (root/'public-export.json').exists() else 'webui/r4.6')
    result={}
    try:
        for path,(size,pin,_) in ADDITION_OUTPUT_RECORDS.items():
            source=base/path.removeprefix('www\\').replace('\\','/')
            result[path]=r2.require_exact(source.read_bytes(),size,pin,path)
    except (OSError,r2.CommunityR2Error) as exc:raise CommunityR46Error(str(exc)) from exc
    return result

def build_patch_set(records,root):
    # Reject altered new assets before deriving any inherited source.
    additions=assets(root)
    try:replacements,_,removals=previous.build_patch_set(records,root)
    except previous.CommunityR45Error as exc:raise CommunityR46Error(str(exc)) from exc
    replacements={path:_revise(data) if path in ('www\\index.html','www\\html\\adminApp.html') else data for path,data in replacements.items()}
    if set(replacements)!=set(OUTPUT_RECORDS):raise CommunityR46Error('R46 replacement set changed')
    try:
        for path,(size,pin) in OUTPUT_RECORDS.items():r2.require_exact(replacements[path],size,pin,path)
    except r2.CommunityR2Error as exc:raise CommunityR46Error(str(exc)) from exc
    return replacements,additions,removals
