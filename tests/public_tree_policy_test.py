import hashlib
import subprocess
import sys
import unittest
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ICON_HASHES = {'firmware/community-0.4.7-dev.15/web/favicon.png': '7cf2c894a867695a1aa4554114af0fd563dfc91afc7e590e3bc2f1585d600c44', 'webui/0.4.7-dev.15/c047d15favicon.png': '7cf2c894a867695a1aa4554114af0fd563dfc91afc7e590e3bc2f1585d600c44', 'firmware/community-0.4.7-dev.15/web/apple-touch-icon.png': 'a3c18e92b3892c95f8cda1b275c73a891f2a0eecd2ce25ad97f1edde4c32d76f', 'webui/0.4.7-dev.15/c047d15touch.png': 'a3c18e92b3892c95f8cda1b275c73a891f2a0eecd2ce25ad97f1edde4c32d76f'}
FORBIDDEN_SUFFIXES = {
    ".bin", ".fbf", ".img", ".rom", ".fw", ".dump", ".pcap",
    ".pcapng", ".har", ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".zip", ".rar", ".7z",
}
FORBIDDEN_PARTS = {
    ".runtime", "build", "evidence", "reverse-engineered-api",
    "node_modules", "scheduled",
}
FORBIDDEN_PATH_MARKERS = (
    "mf885_mini_", "mf885_usb_minsys", "mf885_vds_restore",
)
FORBIDDEN_TEXT = (
    b"/home/shelluser/", b"/root/.mf885", b".runtime/private/",
    b"docs/evidence/", b"docs/reverse-engineered-api/",
)


def repository_files():
    manifest = ROOT / "public-export.json"
    if manifest.is_file():
        sys.path.insert(0, str(ROOT / "tools"))
        import mf885_public_export as public_export

        entries = public_export.collect(public_export.load_manifest(manifest))
        return [(relative, data) for relative, (_, data) in entries.items()]
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    paths = [Path(value.decode("utf-8")) for value in result.stdout.split(b"\0") if value]
    return [(relative, (ROOT / relative).read_bytes()) for relative in paths]


class PublicTreePolicyTest(unittest.TestCase):
    def test_public_tree_contains_source_only_material(self):
        files = repository_files()
        self.assertGreater(len(files), 20)
        for relative, data in files:
            if relative == Path("tests/public_tree_policy_test.py"):
                continue
            if str(relative) in SOURCE_ICON_HASHES:
                self.assertEqual(hashlib.sha256(data).hexdigest(), SOURCE_ICON_HASHES[str(relative)], relative)
                continue
            lowered = str(relative).lower()
            self.assertFalse(any(part in FORBIDDEN_PARTS for part in relative.parts), relative)
            self.assertNotIn(relative.suffix.lower(), FORBIDDEN_SUFFIXES, relative)
            self.assertFalse(any(marker in lowered for marker in FORBIDDEN_PATH_MARKERS), relative)
            self.assertLessEqual(len(data), 2_000_000, relative)
            self.assertNotIn(b"\0", data, relative)
            for marker in FORBIDDEN_TEXT:
                self.assertNotIn(marker, data, f"{relative}: {marker!r}")

        sources = {str(relative): data.decode("utf-8") for relative, data in files if str(relative) not in SOURCE_ICON_HASHES}
        self.assertNotRegex(sources["scriptable.js"], r"\brunFirmwareRestore\b")
        self.assertNotIn("firmwareFlash", sources["scriptable.js"])
        self.assertNotIn("firmwareFlash", sources["modules/ui-v2.js"])
        self.assertNotIn("firmwareFlash", sources["modules/ui-v2-fixes.js"])
        self.assertNotRegex(sources["modules/firmware-stage0.js"], r"\bsendOnce\b")


if __name__ == "__main__":
    unittest.main()
