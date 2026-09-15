"""Private dev18 theme: System/Light/Dark for the browser interface only.

Derived from the dev18 TTL step in release.py. This module rewrites browser
bytes and adds two local source assets (theme.js, theme.css, both beside this
file). It does not touch the native component, the golden/stock inputs, any
earlier release's assets, any released pin, authentication, TTL semantics, or
the favicon/touch bytes and their head references.

Design:
  - `apply_theme()` is a pure dev18-asset -> dev18-asset transform, exactly like
    `apply_ttl_editor()`, so the regression suite exercises the real production
    transform and final pins still come from build_stages.py `webpins`.
  - Theme CSS/JS are versioned assets with their own keys and head references:
    www\\css\\c047d18theme.css and www\\js\\c047d18theme.js. The favicon and
    apple-touch-icon references are left byte-for-byte alone.
  - The early-apply inline script is generated from theme.js between the
    INLINE_START/INLINE_END markers, so the local file stays the single source
    of truth and the colour scheme is on <html> before first paint (no flash).
  - The resolved theme is exposed as data-theme/data-theme-choice on <html>.
    Light is the legacy palette and needs no new rules; the theme stylesheet
    only adds the dark palette and the compact selector.
  - No network access, no timers, no storage other than the validated, try/catch
    wrapped localStorage preference.
"""
import hashlib, re
from pathlib import Path
HERE = Path(__file__).resolve().parent

# theme.py is imported *by* release.py while release.py is still executing, so it
# must not import release.py back. The three shared names it needs (`once`, the
# dev18 Error class and the dev18 asset keys) are injected by release.py through
# bind() immediately after the module is executed. Until then, calling
# apply_theme() fails loudly instead of guessing.
_binding = None

class Error(RuntimeError):
    pass

def bind(namespace):
    """Wire the shared dev18 names in from release.py (called once, at import).

    `namespace` is the executing release module; a plain mapping is accepted too
    because spec_from_file_location callers may not register the module in
    sys.modules, in which case only the frame globals are available.
    """
    global _binding
    _binding = namespace

def _get(name):
    if _binding is None:
        raise Error('theme.py must be bound to the dev18 release module before use')
    if isinstance(_binding, dict):
        return _binding[name]
    return getattr(_binding, name)

def _once(raw, old, new):
    return _get('once')(raw, old, new)

THEME_CSS_KEY = r'www\css\c047d18theme.css'
THEME_JS_KEY = r'www\js\c047d18theme.js'
UI_CSS_KEY = r'www\css\c047d18ui.css'
ENTRY_KEY = r'www\c047d18.html'
APP_OUT = r'www\js\c047d18app.js'

THEME_CSS = (HERE / 'theme.css').read_bytes()
THEME_JS = (HERE / 'theme.js').read_bytes()

# --- Early-apply inline script ------------------------------------------------
# Bounded slice of theme.js: the key/choice constants plus the storage read,
# validation, media-query and paint helpers. It runs synchronously in <head>
# and returns before the deferred modules load. The slice is self-contained (it
# never references the module wrapper or the exported API object), so the local
# theme.js file remains the single source of truth for both copies.
INLINE_START = b"  var KEY = "
INLINE_END = b"  function create(w) {"
INLINE_ANCHOR = b'  <script defer src="js/c047d18app.js"></script>\n'

def inline_script():
    start = THEME_JS.index(INLINE_START)
    end = THEME_JS.index(INLINE_END)
    body = THEME_JS[start:end].rstrip()
    tail = (b"\nvar html=w.document.documentElement;if(html){var choice=readSaved(w);"
            b"html.setAttribute('data-theme-choice',choice);"
            b"html.setAttribute('data-theme',resolve(w,choice));}"
            b"})(window);</script>\n")
    return b'  <script>(function(w){\'use strict\';\n' + body + tail

# --- Head wiring --------------------------------------------------------------
# The theme stylesheet follows the existing ui/ttl stylesheets so it wins on
# equal specificity. The theme module loads first among the deferred scripts so
# the selector exists before the core module binds. Nothing else in the head is
# reordered, and the favicon/touch links are not touched.
HEAD_CSS_OLD = b'  <link rel="stylesheet" href="css/c047d18ttl.css">\n'
HEAD_CSS_NEW = HEAD_CSS_OLD + b'  <link rel="stylesheet" href="css/c047d18theme.css">\n'

def _entry_theme(entry):
    if b'c047d18theme.css' in entry or b'c047d18theme.js' in entry:
        raise Error('entry already carries the dev18 theme references')
    entry = _once(entry, HEAD_CSS_OLD, HEAD_CSS_NEW)
    return _once(entry, INLINE_ANCHOR, inline_script() + b'  <script defer src="js/c047d18theme.js"></script>\n' + INLINE_ANCHOR)

# --- Palette wiring -----------------------------------------------------------
# Two legacy literals are aliased to the theme variables so the dark palette can
# reach them without editing the light rules: the console reply surface already
# reads --surface-soft, and the TTL persistence note already reads --bg. The
# addition is additive and the light values are unchanged.
CONSOLE_CSS_OLD = b"background:var(--surface-soft,#f3f6fa)"
CONSOLE_CSS_NEW = b"background:var(--surface-soft,#f3f6fa);border:1px solid var(--border,transparent)"

def _ui_css(assets):
    raw = assets[UI_CSS_KEY]
    return dict(assets, **{UI_CSS_KEY: _once(raw, CONSOLE_CSS_OLD, CONSOLE_CSS_NEW)})

THEME_STEPS = (_entry_theme,)

def apply_theme(assets):
    """Pure dev18-asset -> dev18-asset transform used by derive() and the tests.

    Input keys and bytes must already carry the dev18 names and the applied TTL
    editor, exactly as release.derive() produces them before this step runs.
    """
    for key in (APP_OUT, ENTRY_KEY, UI_CSS_KEY):
        if key not in assets:
            raise Error('dev18 theme asset missing: ' + key)
    out = dict(assets)
    out[ENTRY_KEY] = _entry_theme(assets[ENTRY_KEY])
    out[THEME_CSS_KEY] = THEME_CSS
    out[THEME_JS_KEY] = THEME_JS
    out = _ui_css(out)
    return out

def theme_pins(assets):
    """Report the theme keys and their hashes for pin review, without writing."""
    keys = [THEME_CSS_KEY, THEME_JS_KEY, APP_OUT, ENTRY_KEY, UI_CSS_KEY]
    return {k: {'bytes': len(assets[k]), 'sha256': hashlib.sha256(assets[k]).hexdigest()} for k in keys}

def head_references(entry):
    """Return the theme references actually present in an entry asset."""
    text = entry.decode('utf-8', 'replace')
    return {
        'css': sorted(re.findall(r'href="(css/c047d18theme\.css)"', text)),
        'js': sorted(re.findall(r'src="(js/c047d18theme\.js)"', text)),
        'inline': text.count('data-theme-choice'),
    }
