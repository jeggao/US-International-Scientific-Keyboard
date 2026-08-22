# Contributing

Thanks for helping improve the US International Scientific keyboard layout!
This page covers the mechanics of changing the layout; the design principles
that decide *which* character belongs on *which* key are in
[Core Design Ideas](README.md#core-design-ideas).

## How the repository fits together

`US International Scientific.klc` is the single source of truth. Everything else
describes the same key mappings a second time and therefore has to be kept in
step with it:

| File | What it is | Kept in step by |
|------|------------|-----------------|
| `US International Scientific.klc` | The MSKLC 1.4 source the `.dll` is built from | — |
| `README.md` | Every key mapping and every dead key, with justifications | `tools/validate.py` |
| `assets/keyboard-layout.json` | [keyboard-layout-editor.com](http://www.keyboard-layout-editor.com/) source for the overview picture | `tools/validate.py` |
| `assets/keyboard-layout.png` | The overview picture itself, exported from that editor | by hand — see below |
| `assets/sandbox.ipynb` | A scratch pad for looking at the layout's characters | executed in CI |

## Running the checks

The checks are pure standard-library Python, so no installation is needed:

```sh
python3 tools/validate.py          # --strict also fails on warnings
```

They report, with file and line number, anything that has drifted:

- a `U+XXXX` code point, character name or sample character in a README table
  that does not match the `.klc`;
- a dead key whose documented base and composite characters have fallen out of
  step, or whose default character is wrong;
- a key or dead key base that the layout provides but the README never mentions;
- a caption in `keyboard-layout.json` that does not match the key it sits on, or
  a colour outside the palette the README legend defines;
- structural problems: broken Markdown tables, links to headings that do not
  exist, missing image files, stray zero-width characters;
- `.klc` problems: a `// ...` comment that no longer lists the characters the
  row produces, a dead key declared in `LAYOUT` with no `DEADKEY` section, a
  `KEYNAME_DEAD` entry that is not the Unicode name of its root, a duplicated
  base inside a dead key, or a character outside the limits MSKLC 1.4 can build.

To work on the checks themselves:

```sh
pip install -r tools/requirements-dev.txt
pytest                    # tests for the parser and every check
ruff check tools          # lint
ruff format tools         # format
```

`.github/workflows/ci.yml` runs all of the above on every push and pull request.

## Changing the layout

1. Open the `.klc` in [MSKLC 1.4](https://www.microsoft.com/en-us/download/details.aspx?id=102134),
   make the change and save. Keep the constraints in
   [Notes on MSKLC 1.4](README.md#notes-on-msklc-14) in mind: every character
   must be in the BMP (U+0000–U+FFFF) and every dead key base must be
   U+0FFF or below.
2. Bump the version in the `KBD` line **and** in the `DESCRIPTIONS` section —
   the two have to agree, and the version is what users see on the taskbar.
3. Update the matching table in `README.md`, including the character name, which
   must be the exact Unicode name.
4. Update `assets/keyboard-layout.json`. Re-import it into
   [keyboard-layout-editor.com](http://www.keyboard-layout-editor.com/), export
   the picture and replace `assets/keyboard-layout.png`. Make sure no key is
   left selected when you take the export, or its outline ends up in the image.
5. Run `python3 tools/validate.py` and fix whatever it reports.

### Editing the `.klc` by hand

MSKLC writes the file as **UTF-16LE with a byte order mark and CRLF line
endings**, and refuses to open it in any other encoding. `.gitattributes` stops
git from normalising it, but an editor still can — check with
`file "US International Scientific.klc"` after saving, and note that
`tools/validate.py` and the `klc-encoding` CI job both verify this.

Two conventions the checks enforce, so that the file stays readable:

- every `LAYOUT` row ends with a `// ...` comment listing the Unicode name of
  each column, with `<none>` for an unassigned (`-1`) column;
- every `DEADKEY` line ends with a `// b -> c` comment showing the two
  characters involved.

### Showing a combining mark

A combining mark on its own attaches to whatever precedes it, which in a
Markdown table is the `|`. Write it on a dotted circle instead — `◌̈`, U+25CC
followed by the mark — or, in the *Char* column of a key table, use the dead
key's default character, which is the spacing form of the same diacritic.
