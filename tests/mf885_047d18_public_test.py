"""Public dev18 closure and production transform regression; no live IO."""
import hashlib, importlib.util, json, subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Dev18PublicTest(unittest.TestCase):
 def test_public_native_closure_loads_and_checks_all_pins(self):
  code="import sys;sys.path[:0]=['firmware/community-0.4.7-dev.18','tools'];import builder;builder.native.architecture_inputs();assert builder.native.COMPONENT_SHA=='76df60de2f1f99a52b81db3576c2b5cd280a10d231164f61f726ed31eab4c9fd';from mf885_console_component_v7 import derive_report;derive_report()"
  result=subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
 def test_exported_assets_and_production_derivation_match_pins(self):
  sys.path.insert(0,str(ROOT/'tools'))
  spec=importlib.util.spec_from_file_location('dev18_public_transform',ROOT/'firmware/community-0.4.7-dev.18/release.py')
  release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
  base=ROOT/'webui/0.4.7-dev.15'
  initial={'www\\'+str(p.relative_to(base)).replace('/','\\'):p.read_bytes() for p in base.rglob('*') if p.is_file()}
  v17=release.previous;v16=v17.previous;v15=v16.previous
  v17.build_patch_set=v17.derive;v16.build_patch_set=v16.derive;v15.build_patch_set=lambda records,root:({},initial,[])
  _,derived,_=release.derive({},ROOT)
  base=ROOT/'webui/0.4.7-dev.18'
  actual={'www\\'+str(p.relative_to(base)).replace('/','\\'):p.read_bytes() for p in base.rglob('*') if p.is_file()}
  self.assertEqual(derived,actual)
  pins=json.loads((ROOT/'firmware/community-0.4.7-dev.18/web-pins.json').read_text())
  self.assertGreaterEqual(len(actual),16)
  for key,data in actual.items():self.assertEqual({'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()},pins[key],key)
 def test_wrapper_rejects_without_ack_before_input(self):
  r=subprocess.run([sys.executable,'-B',str(ROOT/'tools/mf885_build_variant.py'),'--variant','community-0.4.7-dev.18'],capture_output=True)
  self.assertEqual(r.returncode,2);self.assertIn(b'acknowledge',r.stderr)
if __name__=='__main__':unittest.main()
