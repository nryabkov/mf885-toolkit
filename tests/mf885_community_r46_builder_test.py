"""R4.6 source/pin checks; exact-container tests require owner-supplied inputs."""
import hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import mf885_community_r46 as release
import mf885_community_r46_native_builder as builder
import mf885_webui_stage_builder as stage
import mf885_build_variant as wrapper
import mf885_firmware_inspect as inspector
import mf885_webi_builder as webi
GOLDEN=Path(os.environ.get('MF885_TEST_GOLDEN',str(ROOT/'input/MF885_golden.bin')))
IDENTITY=Path(os.environ.get('MF885_TEST_IDENTITY',str(ROOT/'input/mf885-base.xml')))
class SourceTests(unittest.TestCase):
    def test_assets_exact_pins_and_manifest(self):
        assets=release.assets(ROOT);self.assertEqual(len(assets),5)
        base=ROOT/('public/webui/r4.6' if (ROOT/'public-export.json').exists() else 'webui/r4.6')
        manifest=json.loads((base/'manifest.json').read_text())
        expected={name.removeprefix('www\\').replace('\\','/'):{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in assets.items()}
        self.assertEqual(manifest['files'],expected)
        self.assertIn(release.MARKER,b'\n'.join(assets.values()))
        self.assertNotIn(b'setInterval',assets[release.TTL_APP_PATH]);self.assertNotIn(b'setTimeout',assets[release.TTL_APP_PATH])
        self.assertNotIn(b'bodyRedacted:false',assets[release.APP_PATH])
    def test_missing_or_altered_assets_fail_before_parent_derivation(self):
        with tempfile.TemporaryDirectory() as d,patch.object(release.previous,'build_patch_set') as parent:
            with self.assertRaises(release.CommunityR46Error):release.build_patch_set({},Path(d))
            parent.assert_not_called()
    def test_profile_is_separate_and_qualification_is_truthful(self):
        safety=stage.STAGE_PROFILES[release.PROFILE]['safety'];self.assertEqual(safety['ttlMode'],'native-ram-editor')
        self.assertEqual(safety['ttlAutomaticRequests'],0);self.assertEqual(safety['ttlBrowserPostRequestsPerChange'],1)
        self.assertFalse(safety['ttlPacketPathQualified']);self.assertFalse(safety['rawResponseBodiesLogged'])
        self.assertEqual(stage.STAGE_PROFILES['0.4.5-community-r2']['safety']['ttlFixedValue'],64)
        self.assertFalse(builder.QUALIFICATION['flash_qualified']);self.assertFalse(builder.QUALIFICATION['live_dynamic_ttl_verified'])
    def test_wrapper_rejects_hardware_failed_profile(self):
        with tempfile.TemporaryDirectory() as d,patch.object(builder,'main',return_value=17) as run:
            self.assertEqual(wrapper.main(['--variant','community-r4.6','--output-dir',d,'--acknowledge-brick-risk']),2)
            run.assert_not_called()
    def test_ack_and_existing_outputs_fail_before_build(self):
        with tempfile.TemporaryDirectory() as d,patch.object(builder.comparator,'build_candidate') as build:
            out=Path(d)/'image.bin';report=Path(d)/'report.json'
            args=['--golden',str(GOLDEN),'--identity-xml',str(IDENTITY),'--output',str(out),'--report',str(report)]
            self.assertEqual(builder.main(args),2);out.write_bytes(b'keep');self.assertEqual(builder.main(args+[builder.CONFIRMATION_FLAG]),2)
            build.assert_not_called();self.assertEqual(out.read_bytes(),b'keep');self.assertFalse(report.exists())
@unittest.skipUnless(GOLDEN.is_file(),'optional exact stock backup')
class GoldenAssetsTests(unittest.TestCase):
    def test_exact_golden_derived_records(self):
        raw=GOLDEN.read_bytes();_,records,_=webi.parse_cafe_source(raw[0x52023c:0x52023c+0x1c0000])
        replacements,additions,removals=release.build_patch_set({r.path:r.logical_data for r in records},ROOT)
        self.assertEqual(set(additions),set(release.ADDITION_OUTPUT_RECORDS));self.assertEqual(len(replacements),6)
        self.assertIn(b'href="/r46.html"',replacements['www\\index.html']);self.assertIn(b'href="/r46.html"',replacements['www\\html\\adminApp.html'])
@unittest.skipUnless(GOLDEN.is_file() and IDENTITY.is_file(),'optional exact backup and identity')
class ContainerTests(unittest.TestCase):
    def test_full_container_verification_and_tamper_rejection(self):
        identity=inspector.load_identity(IDENTITY);golden=webi.require_reviewed_golden(GOLDEN,identity)
        image,report=builder.build_candidate(golden,identity)
        result=builder.verify_candidate(golden,image,identity);self.assertEqual(result['status'],'GREEN');self.assertTrue(all(c['passed'] for c in result['conditions']))
        self.assertEqual(len(image),8323644);self.assertEqual(report['native']['artifact']['sha256'],'7c3a8d06b3cdb2d8bdd91eb028d82c103d05e9e8f29b756b7f8c86192e8b30b8')
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'candidate.bin';path.write_bytes(image);self.assertEqual(inspector.inspect_image(path,identity,include_records=True).report['verification']['status'],'verified')
        _,parts=builder.shared._partition_map(golden,identity)
        for p in parts:
            if p.name not in ('OSLO','WEBI'):self.assertEqual(image[p.offset:p.offset+p.length],golden[p.offset:p.offset+p.length])
        changed=bytearray(image);p=next(p for p in parts if p.name not in ('OSLO','WEBI'));changed[p.offset]^=1
        with self.assertRaises((builder.CommunityR46NativeError,inspector.InspectionError)):builder.verify_candidate(golden,bytes(changed),identity)
if __name__=='__main__':unittest.main()
