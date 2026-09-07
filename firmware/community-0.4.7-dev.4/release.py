"""Private guided TTL editor derived from exact golden assets; no device I/O."""
import hashlib
import json
import re
from pathlib import Path
import mf885_community_r46 as previous

HERE = Path(__file__).resolve().parent
PROFILE = '0.4.7-dev.4'
MARKER = b'MF885 Community 0.4.7-dev.4 - base 2.5.94'
ARTIFACT = 'MF885-Community-0.4.7-dev.4-base-2.5.94.bin'
CAPABILITY = {'schema': 'mf885-ttl-editor/v1', 'communityVersion': PROFILE, 'vendorBase': '2.5.94', 'nativeApi': 'r47-revision24-ttl8', 'settings': ['64', 'off'], 'persistence': 'ram', 'bootTtl': 64}

class Error(RuntimeError):
    pass

def replace_once(raw, old, new):
    if raw.count(old) != 1:
        raise Error('Inherited asset structure changed: ' + repr(old[:80]))
    return raw.replace(old, new)

def revise(raw):
    for old, new in ((previous.MARKER, MARKER), (b'0.4.6-community-r2', b'0.4.7-dev.4'), (b'MF885CommunityR46', b'MF885Community047Dev4'), (b'R4.6', b'0.4.7-dev.4'), (b'0.4.6', b'0.4.7-dev.4'), (b'r46', b'c047d4')):
        raw = raw.replace(old, new)
    return raw

def derive(records, root):
    replacements, old, removed = previous.build_patch_set(records, root)
    replacements = {p: revise(b) if p in ('www\\index.html', 'www\\html\\adminApp.html') else b for p, b in replacements.items()}
    entry = old[previous.ENTRY_PATH]
    entry = replace_once(entry, b'The experimental TTL editor opens after a manual state read. Universal refresh updates device data and messages; TTL is read only on request.', b'Read the router setting to use the TTL editor. TTL changes last until restart. Universal refresh updates device data and messages; TTL is read only on request.')
    entry, count = re.subn(rb'      <section id="page-ttl".*?</section>', lambda _: (HERE / 'web/panel.html').read_bytes().rstrip(b'\n'), entry, flags=re.S)
    if count != 1:
        raise Error('TTL panel structure changed')
    entry, count = re.subn(rb'<footer><span>[^<]+</span>', lambda _: b'<footer><span>' + MARKER + b'</span>', entry)
    if count != 1:
        raise Error('Footer structure changed')
    app = old[previous.APP_PATH]
    # Keep the proven login/API URI split and shared router-operation lock.
    # Refuse entity, PI, comment, CDATA and non-ASCII envelopes before DOM parsing.
    old_doc = b"if(reply.body.length>4096||/<!DOCTYPE|<!ENTITY/i.test(reply.body))"
    new_doc = b"if(!reply.body.length||reply.body.length>4096||/[^\\x09\\x0a\\x0d\\x20-\\x7e]/.test(reply.body)||/<!|&/.test(reply.body)||/<\\?/.test(reply.body.replace(/^\\s*<\\?xml\\s[^?]*\\?>/,'')))"
    app = replace_once(app, old_doc, new_doc)
    old_value = b"!(value==='off'||/^[1-9][0-9]{0,2}$/.test(value)&&Number(value)<=255)"
    app = replace_once(app, old_value, b"!(value==='off'||value==='64')")
    old_bridge = b"    get:function(owner){ttlTransportOwner(owner);"
    app = replace_once(app, old_bridge, b"    capability:function(owner){ttlTransportOwner(owner);return request({method:'GET',url:'/c047d4ttl.json',owner:owner}).then(function(reply){return reply.body})},\n" + old_bridge)
    assets = {
        'www\\c047d4.html': revise(entry),
        'www\\js\\c047d4app.js': revise(app),
        'www\\css\\c047d4ui.css': old[previous.CSS_PATH],
        'www\\js\\c047d4ttl.js': (HERE / 'web/ttl.js').read_bytes(),
        'www\\css\\c047d4ttl.css': (HERE / 'web/ttl.css').read_bytes(),
        'www\\c047d4ttl.json': (json.dumps(CAPABILITY, separators=(',', ':')) + '\n').encode(),
    }
    if MARKER not in assets['www\\c047d4.html'] or b'r46:' in assets['www\\js\\c047d4ttl.js']:
        raise Error('Version/API mismatch')
    return replacements, assets, removed

def build_patch_set(records, root):
    replacements, assets, removed = derive(records, root)
    expected = json.loads((HERE / 'web-pins.json').read_bytes())
    actual = {p: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} for p, raw in {**replacements, **assets}.items()}
    if actual != expected:
        raise Error('Guided editor asset pin mismatch')
    return replacements, assets, removed
