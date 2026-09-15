"""Rebuild exact stock + cumulative TTL + combined native console with CPU accounting."""
import json,tempfile,hashlib,os
from pathlib import Path
from mf885_console_component_v7 import build as build_component
from mf885_console_legacy_build_v5 import STOCK_SHA,REPO
HERE=Path(__file__).resolve().parent
# Independently rebuilt and executed console v7 + unchanged cumulative TTL.
COMPONENT_SHA='76df60de2f1f99a52b81db3576c2b5cd280a10d231164f61f726ed31eab4c9fd'
ELF_SHA='af280fbc2bc278378478bd169f6eb1ecc0df7ed48f430ed3e1b0f01cec60ff72'
TOOLCHAIN=Path(os.environ.get('MF885_TOOLCHAIN_ROOT', str(REPO/'input/clang18')))
def architecture_inputs():
 pins=json.loads((HERE/'native-source-pins.json').read_text())
 for name,pin in pins.items():assert hashlib.sha256((REPO/name).read_bytes()).hexdigest()==pin,name
 return {'target':'ARMv5TE ARM/Thumb1 LE EABI5 soft-float','runtime':'88MP1802 ARM9, base2.5.94/MF96 Ver.D','native_units':'console, boot/trampolines, USSD C/LTO and dev2 TTL independently inspected; ARM926 is compatibility profile','dev17_change':'native CPU idle accounting and three reviewed ARM hooks; browser CPU interval display'}
def build_payload(oslo):
 architecture_inputs();assert hashlib.sha256(oslo).hexdigest()==STOCK_SHA
 with tempfile.TemporaryDirectory(prefix='mf885-dev17-native-',dir='/tmp') as directory:
  root=Path(directory);stock=root/'stock-oslo.bin';stock.write_bytes(oslo);out=root/'component'
  build_component(TOOLCHAIN,stock,out)
  component=(out/'unqualified-oslo.component.bin').read_bytes();report=json.loads((out/'COMPONENT.json').read_text())
  old=json.loads((out/'legacy/COMPONENT.json').read_text());ttl=json.loads((out/'legacy/TTL-BASELINE.json').read_text())
  assert hashlib.sha256(component).hexdigest()==COMPONENT_SHA and report['inspection']['elf_sha256']==ELF_SHA
  # Two intended callback pointers replace legacy pointers at identical ranges.
  # Other ranges must remain non-overlapping; shared container checker enforces it.
  changes={(x['offset'],x['bytes']):x for x in ttl['changed_ranges']+old['patches']}
  for x in report['patches']:
   item={'name':x['name'],'offset':x['address']-0x06000000,'bytes':x['bytes']};changes[(item['offset'],item['bytes'])]=item
  return component,{'schema':'mf885-047d17-native/v1','changed_ranges':list(changes.values()),'contract':ttl['contract'],
   'console':report,'ussd':old,'architecture_build':json.loads((out/'legacy/synthetic/BUILD.json').read_text()),
   'architecture_object':json.loads((out/'legacy/OBJECT.json').read_text()),'architecture_lto':json.loads((out/'legacy/LTO.json').read_text()),
   'device_actions':0,'hardware_qualified':False,'cpu_native_v1':True}
