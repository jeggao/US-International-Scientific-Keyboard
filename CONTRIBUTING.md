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
| `dist/macos/US-International Scientific.keylayout` | **Generated.** The macOS layout | `tools/generate.py` |
| `assets/keyboard-layout.svg` | **Generated.** The overview picture, self-contained | `tools/generate.py` |
| `assets/keyboard-layout.json` | **Generated.** The same picture as [keyboard-layout-editor.com](http://www.keyboard-layout-editor.com/) source | `tools/generate.py` |
| `assets/keyboard-layout.png` | **Built** from the SVG by a headless browser | `tools/render.py`, and CI |
| `README.md` | Every key mapping and every dead key, with justifications | `tools/validate.py` |
| `assets/sandbox.ipynb` | A scratch pad for looking at the layout's characters | executed in CI |

Nothing generated should ever be edited by hand: `tools/generate.py --check`
fails the build if a generated file does not match what the source produces.

## Changing the layout

```sh
$EDITOR layout/us-intl-scientific.toml
python3 tools/generate.py     # rewrite every platform file and the picture source
python3 tools/render.py       # redraw assets/keyboard-layout.png
python3 tools/validate.py     # check the documentation still matches
```

Then update the affected table in `README.md`. When the layout itself changes,
bump `version` in the source; it is what users see on the Windows taskbar, and it
appears in the `.klc` in two places that have to agree.

You do not have to run `tools/render.py` yourself — CI rebuilds the picture on
every push and commits it back if it changed. It is only there so you can see
the result before pushing.

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

## The picture

`assets/keyboard-layout.png` is what README.md shows, and it is built in two
steps. `tools/generate.py` draws the layout into `assets/keyboard-layout.svg`,
which is plain text and therefore diffable and checked for drift like every
other generated file; `tools/render.py` then rasterises that SVG with a headless
Chromium.

When CI does rebuild the picture, it commits the result to the branch itself.
A push made with the workflow's own token deliberately does not start another
workflow run -- otherwise the job would trigger itself forever -- so that new
commit arrives with no checks attached, and the pull request will say it has
none until something else is pushed. The checks on the commit before it still
stand; nothing has failed.

The SVG carries its own font — a subset of DejaVu Sans covering exactly the
characters the picture draws, embedded as a data URI — so it renders the same
whatever fonts the machine happens to have, and the PNG comes out identical on
any machine with the same browser. If you add a character the subset does not
cover, `pytest` says so; regenerate it with `python3 tools/subset_font.py`,
which needs `fonttools`, `brotli` and DejaVu Sans installed.

Which colour a keycap and its labels take is decided in
`tools/kbdlayout/generators/picture.py` and follows README.md's legend. The one
judgement in there is when to draw a dead key's root character next to its
default: only when the root is something the dead key can actually produce and
is not a diacritic whose spacing form already stands for it, which is why <kbd>&</kbd>,
<kbd>E</kbd> and <kbd>A</kbd> show a pair and <kbd>H</kbd>, <kbd>Z</kbd> and <kbd>M</kbd> do not.

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

**macOS** is implemented, in `generators/macos_keylayout.py`, but has never been
loaded by macOS. What the tests establish is that the file is well formed, that
every key and every level agrees with the layout, and that all 2,660 dead key
results match the Linux Compose file character for character. What they cannot
establish is that macOS accepts the grammar at all.

Two decisions in there are worth knowing about, because both work around
behaviour Apple's format leaves to the implementation:

- **Every dead key gets an explicit entry for every printable ASCII base**, not
  only the ones it composes, so an unmapped base produces the root character
  followed by the base character — what Windows does, and what the generated
  Compose file does on Linux. That makes the behaviour independent of how macOS
  treats a missing `when`. `terminators` then holds each dead key's *root*, for
  the case where a dead key is abandoned by a key outside that range.
- **`anyControl?` is on the Option key maps**, because README.md tells users the
  AltGr states are reachable by holding Control and Alt together, and without it
  Control+Option would fall through to the plain characters.

Three things still want checking on a real Mac:

- The **virtual key codes for the keys this layout does not change** — Return,
  Tab, Escape, the arrows, the function keys, the keypad. A `.keylayout`
  describes the whole keyboard, and a key missing from a `keyMap` produces
  nothing, so they have to be there. The graphic keys are derived from
  `/usr/share/X11/xkb/keycodes/macintosh` and all 50 agree with Apple's
  published constants; the rest are the conventional values.
- The **arrow keys specifically**. That X11 table puts them at 59–62 and the
  right-hand modifiers at 123–126, while Apple's constants have the arrows at
  123–126. The generator follows Apple. The modifiers never appear in a `keyMap`
  either way, so only the arrows are at risk.
- Whether the file needs a **bundle** rather than a loose `.keylayout` to carry
  an icon, and whether macOS caches layouts across a reinstall.

## Showing a combining mark

A combining mark on its own attaches to whatever precedes it, which in a
Markdown table is the `|`. Write it on a dotted circle instead — `◌̈`, U+25CC
followed by the mark — or, in the *Char* column of a key table, use the dead
key's default character, which is the spacing form of the same diacritic.
