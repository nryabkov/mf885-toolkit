"""Public dependency and qualified-asset contracts; no device/native build."""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
class Dev15PublicTest(unittest.TestCase):
    def test_native_dependencies_are_pinned_and_present(self):
        pins = json.loads((ROOT/'firmware/community-0.4.7-dev.15/native-source-pins.json').read_text())
        for name, expected in pins.items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), expected, name)
    def test_served_community_assets_match_hardware_release(self):
        pins = json.loads((ROOT/'firmware/community-0.4.7-dev.15/web-pins.json').read_text())
        files = [p for p in (ROOT/'webui/0.4.7-dev.15').rglob('*') if p.is_file()]
        self.assertEqual(len(files), 12)
        for p in files:
            key = 'www\\'+str(p.relative_to(ROOT/'webui/0.4.7-dev.15')).replace('/', '\\')
            raw = p.read_bytes()
            self.assertEqual({'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}, pins[key])
    def test_new_wrapper_rejects_missing_acknowledgement_before_input(self):
        r = subprocess.run([sys.executable,'-B',str(ROOT/'tools/mf885_build_variant.py'),'--variant','community-0.4.7-dev.15'],capture_output=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn(b'acknowledge',r.stderr)
    def test_native_adapter_has_no_prebuilt_cache(self):
        raw = (ROOT/'firmware/community-0.4.7-dev.15/native_payload.py').read_text()
        self.assertNotIn('cached_dev14_payload',raw)
        self.assertIn('MF885_TOOLCHAIN_ROOT',raw)
if __name__ == '__main__':unittest.main()
