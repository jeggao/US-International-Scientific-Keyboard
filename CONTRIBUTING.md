# Contributing

Thanks for helping improve the US International Scientific keyboard layout!
This page covers the mechanics of changing the layout; the design principles
that decide *which* character belongs on *which* key are in
[Core Design Ideas](README.md#core-design-ideas).

## How the repository fits together

`layout/us-intl-scientific.toml` is the single source of truth. Every other file
either comes out of it or is checked against it:

| File | What it is | Kept in step by |
|------|------------|-----------------|
| `layout/us-intl-scientific.toml` | The layout: 50 keys, 28 dead keys, and what each platform calls them | — |
| `US International Scientific.klc` | **Generated.** MSKLC 1.4 source, built into the Windows `.dll` | `tools/generate.py` |
| `dist/linux/symbols/us_intl_sci` | **Generated.** XKB symbols file | `tools/generate.py` |
| `dist/linux/us_intl_sci.XCompose` | **Generated.** Compose sequences for the dead keys | `tools/generate.py` |
| `README.md` | Every key mapping and every dead key, with justifications | `tools/validate.py` |
| `assets/keyboard-layout.json` | [keyboard-layout-editor.com](http://www.keyboard-layout-editor.com/) source for the overview picture | `tools/validate.py` |
| `assets/keyboard-layout.png` | The overview picture itself, exported from that editor | by hand — see below |
| `assets/sandbox.ipynb` | A scratch pad for looking at the layout's characters | executed in CI |

Nothing generated should ever be edited by hand: `tools/generate.py --check`
fails the build if a generated file does not match what the source produces.

## Changing the layout

```sh
$EDITOR layout/us-intl-scientific.toml
python3 tools/generate.py     # rewrite the Windows and Linux files
python3 tools/validate.py     # check the documentation still matches
```

Then update the affected table in `README.md`, and — if a key's caption changed —
`assets/keyboard-layout.json` and the picture exported from it. When the layout
itself changes, bump `version` in the source; it is what users see on the Windows
taskbar, and it appears in the `.klc` in two places that have to agree.

`tools/validate.py` reports, with file and line number, anything that has
drifted: a `U+XXXX`, character name or sample character in a README table that
no longer matches, a dead key whose documented bases and composites have fallen
out of step, a key the layout provides but the README never mentions, a caption
or a palette colour in the picture source that disagrees with the layout, and
structural problems like broken Markdown tables or links to headings that do not
exist.

## The layout file

```toml
[[key]]                        # keys are named by ISO/IEC 9995 position
id = "AD01"                    # AD01 is the Q key on any keyboard
normal = "q"
shift = "Q"
altgr = "÷"
altgr_shift = { dead = "U+2261" }   # this shift state starts a dead key

[[dead_key]]
root = "U+030C"                # the character the key stands for
category = "Caron diacritic"   # the heading it is documented under
xkb_leader = "dead_caron"      # the keysym Linux puts on the key
map = [
  ["n", "ň"],
  ["U+0020", "U+02C7"],        # the space bar gives the default character
]
```

A character is written either as itself or, when it is invisible or would not
survive being pasted around — a space, a control character, a combining mark —
as `"U+XXXX"`. A shift state a key does not use is simply omitted. `caps` is
derived from whether the unmodified and Shift characters are a case pair, and
only needs writing out to override that.

Constraints the loader enforces, so that a layout that cannot be built never
reaches a generator: every character must be in the BMP (U+0000–U+FFFF), every
dead key root and base must be U+0FFF or below (both are
[MSKLC 1.4 limits](README.md#notes-on-msklc-14)), every dead key needs a U+0020
entry, and no two dead keys may share a Linux keysym.

That last one is easy to get wrong. X11 has several names for the same keysym —
`dead_perispomeni` **is** `dead_tilde`, and `dead_small_schwa` **is**
`dead_schwa` — so two dead keys can collide even though their names differ. The
check compares values, not names.

## Running the checks

The checks are pure standard-library Python, so no installation is needed:

```sh
python3 tools/generate.py --check   # are the generated files current?
python3 tools/validate.py --strict  # does the documentation still match?
```

To work on the tools themselves:

```sh
pip install -r tools/requirements-dev.txt
pytest                    # parser, generators, and every check
ruff check tools          # lint
ruff format tools         # format
```

Some tests compile the generated XKB file with `xkbcomp` and compare the result
against the stock `us` layout; they skip themselves when it is not installed
(`apt install x11-xkb-utils xkb-data`). `.github/workflows/ci.yml` runs
everything on every push and pull request.

## Editing the `.klc` by hand

Don't — it is generated. If you need to import someone else's `.klc`,
`tools/kbdlayout/klc.py` parses one into the same model the TOML loads into.

MSKLC writes the file as **UTF-16LE with a byte order mark and CRLF line
endings** and refuses to open anything else, so `.gitattributes` stops git
normalising it and CI checks the encoding on every run. The generator reproduces
MSKLC's own formatting exactly, down to the tab stops — the test suite asserts
the generated file is byte-for-byte what MSKLC produced before the layout moved
into TOML, which is what proves the move lost nothing.

## Adding a platform

A back end is one module in `tools/kbdlayout/generators/` exposing
`generate(layout) -> {path: content}`, plus one entry in `GENERATORS`. `str`
content is written as UTF-8 with LF endings, `bytes` verbatim. Everything a
platform needs is already in the model; what belongs in the module rather than
in the layout file is the platform's own vocabulary — Windows scan codes and
virtual key names, X11 keysyms — because that is a property of keyboards, not of
this layout.

**macOS** is the obvious next one. A `.keylayout` is a single XML file, and the
model fits it well: every output is one BMP code point, every dead key base is
printable ASCII typeable at the unmodified or Shift level, every dead key has a
default character, and no dead key chains into another. The mapping is
`<keyMapSet>` for the four shift states, one `<action>` per dead key base, one
`<when state=…>` per composition and a `<terminators>` entry per dead key. Three
things need a Mac to settle, and none of them can be answered from this
repository:

- **The fallback rule.** What macOS does when a dead key is followed by a base
  it has no `<when>` for decides whether the terminator should hold each dead
  key's default character or its root character. Windows and the generated Linux
  files both emit the root character followed by the base; matching that is the
  goal.
- **The virtual key codes.** The graphic keys can be derived from
  `/usr/share/X11/xkb/keycodes/macintosh`, but the arrow keys there contradict
  the values Apple documents, and Apple ISO keyboards are a known source of
  transposition between the two keys either side of the alphabetic block.
- **The non-graphic keys.** A `.keylayout` describes the whole keyboard, and a
  key missing from a `keyMap` produces nothing — so Return, Tab, Escape, the
  function keys and the keypad all have to be included even though this layout
  does not change them. Lift them from a layout shipped with macOS rather than
  guessing.

Until someone can test on a Mac, this is deliberately not implemented: an
untested generator that produces a plausible file is worse than no generator.

## Showing a combining mark

A combining mark on its own attaches to whatever precedes it, which in a
Markdown table is the `|`. Write it on a dotted circle instead — `◌̈`, U+25CC
followed by the mark — or, in the *Char* column of a key table, use the dead
key's default character, which is the spacing form of the same diacritic.
