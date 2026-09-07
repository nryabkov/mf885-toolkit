"""Reuse the immutable dev.2 native builder; require byte-identical emitted OSLO."""
import importlib.util
import json
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('mf885_native_047d2_unchanged', HERE.parent / 'community-0.4.7-dev.2/native_payload.py')
native2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native2)
TARGET = native2.TARGET
stock = native2.stock
memory_layout = native2.memory_layout
def architecture_inputs():
    expected = json.loads((HERE / 'native-reuse-pins.json').read_bytes())
    for row in expected['sources']:
        source = (HERE.parents[1] / row['path']).read_bytes()
        if len(source) != row['bytes'] or hashlib.sha256(source).hexdigest() != row['sha256']:
            raise native2.Error('Immutable dev.2 native source pin changed')
    return native2.architecture_inputs()

def build_payload(oslo):
    architecture_inputs()
    result, report = native2.build_payload(oslo)
    expected = json.loads((HERE / 'native-reuse-pins.json').read_bytes())
    if {'bytes': len(result), 'sha256': hashlib.sha256(result).hexdigest()} != expected['oslo']:
        raise native2.Error('Native bytes differ from the installed dev.2 component')
    return result, report
