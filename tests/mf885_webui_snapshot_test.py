"""Ensure published WebUI bytes match the existing pinned on-device source."""
import hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import mf885_community_r45 as release
class WebUiSnapshotTests(unittest.TestCase):
    def test_snapshot_matches_all_three_release_pins(self):
        base=ROOT/('public/webui/r4.5' if (ROOT/'public-export.json').exists() else 'webui/r4.5')
        manifest=json.loads((base/'manifest.json').read_text())
        expected={name.replace('www\\','',1).replace('\\','/'):(size,pin) for name,(size,pin,_) in release.ADDITION_OUTPUT_RECORDS.items()}
        self.assertEqual(set(manifest['files']),set(expected))
        for name,(size,pin) in expected.items():
            raw=(base/name).read_bytes()
            self.assertEqual((len(raw),hashlib.sha256(raw).hexdigest()),(size,pin))
            self.assertEqual(manifest['files'][name],{'bytes':size,'sha256':pin})
if __name__=='__main__':unittest.main()
