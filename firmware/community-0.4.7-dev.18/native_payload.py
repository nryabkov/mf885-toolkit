"""dev18 native shim: reuse the exact reviewed dev17 native component unchanged.

dev18 changes only the browser TTL editor argument range; the native r47 TTL
contract (revision24 / ttl8: `off` or decimal 1..255, boot default 64) is already
what dev17 ships and what dev2 implements. So this module re-exports the dev17
native payload functions verbatim and adds no build step, no new hash and no
native compile. The reported schema is relabelled for dev18 while every
architecture input, source pin, reviewed pin and component/ELF hash is preserved
from dev17.
"""
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mf885_047d18_native_source',HERE.parent/'community-0.4.7-dev.17/native_payload.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
# Unchanged native component and ELF, inherited from the reviewed dev17 build.
COMPONENT_SHA=previous.COMPONENT_SHA
ELF_SHA=previous.ELF_SHA
STOCK_SHA=previous.STOCK_SHA
REPO=previous.REPO
TOOLCHAIN=previous.TOOLCHAIN
SCHEMA='mf885-047d18-native/v1'

def architecture_inputs():
 inputs=dict(previous.architecture_inputs())
 inputs['dev18_change']='no native change: browser TTL editor accepts off or a manual 1..255 (native r47-revision24-ttl8 already implements it)'
 return inputs

def _relabel(report):
 report=dict(report);report['schema']=SCHEMA;report['native_unchanged_from_dev17']=True
 return report

def build_payload(oslo):
 component,report=previous.build_payload(oslo)
 return component,_relabel(report)
