# Architecture review

An evaluation of how this repository is put together, and what I would change.
Every claim below was checked against the code as it stands on `main`
(`ec42d42`); the commands used are in [Appendix: how this was
verified](#appendix-how-this-was-verified).

## Summary

The core architecture is sound and, for a project of this kind, unusually well
considered. One TOML file is the source of truth, a platform-neutral model sits
in the middle, and pluggable back ends emit one platform each. Generated files
are committed *and* re-derived in CI, so consumers never need the toolchain and
drift cannot survive a pull request. That is the right shape.

The weaknesses are not in the shape but in where the seams actually fall. Three
of them matter:

1. The "platform-neutral" model knows about all three platforms, which makes the
   documented "adding a platform is one module plus one registry entry" contract
   untrue.
2. `README.md` is a second source of truth — 364 of its 641 lines are tables
   restating the TOML — and the project carries a 638-line checker to police
   that duplication instead of generating it away.
3. The check orchestration lives inside `cli.main()`, so the test suite
   re-implements it and can silently fall out of step.

Everything else is smaller: packaging, duplicated primitives, a hygiene check
that misses three of the six generated files, and two CI jobs that duplicate
tests.

## What the architecture gets right

Worth stating plainly, because these are the parts not to disturb.

- **One source of truth, enforced rather than asserted.** `generate.py --check`
  fails the build when any generated file drifts, so "do not edit this by hand"
  is a machine-checked rule, not a comment.
- **Generated output is committed.** Users download a `.klc` or an `.XCompose`
  without installing Python. The toolchain is a maintainer tool, not a build
  dependency for consumers.
- **Round-trip and differential verification.** `klc.py` parses the shipped
  `.klc` back and compares it to the source *without* going through the
  generator, so a bug in the generator cannot hide behind itself. The macOS and
  Linux back ends are cross-checked against each other for all 2,660 dead-key
  results. This is real verification, not smoke testing.
- **The deterministic/non-deterministic split in the picture pipeline.** The SVG
  is text, generated everywhere, and diff-checked like any other artifact; only
  the PNG rasterisation needs a browser and is handled separately with a pixel
  tolerance. Getting that boundary in the right place is the single smartest
  decision in the repo.
- **Byte-exactness is pinned where it has to be.** UTF-16LE, BOM, CRLF, tab
  stops — all reproduced deliberately, with `.gitattributes` stopping git from
  normalising the one file that must not be normalised.
- **The comments explain *why*.** Why `FOUR_LEVEL_SEMIALPHABETIC` and not
  `FOUR_LEVEL_ALPHABETIC`; why `<terminators>` holds the root rather than the
  default; why `render.py` returns non-zero instead of quietly passing when no
  browser is present. That last one is a genuinely good instinct: a green check
  that verified nothing is worse than a red one.

## Findings

### P1 — The layering boundary is stated but not held

`model.py` opens with:

> Nothing in this module knows about any particular platform; that belongs in
> `kbdlayout.generators`.

It does not hold. `model.py` currently contains:

| Platform knowledge in `model.py` | Belongs to |
|---|---|
| `MAX_DEAD_KEY_ROOT`, `MAX_CODE_POINT` | MSKLC 1.4 (Windows) |
| `DeadKey.xkb_leader` field | X11 (Linux) |
| `Layout._leader_problems()`, importing `.keysyms` | X11 (Linux) |
| `WindowsTarget`, `LinuxTarget`, `MacosTarget` | all three |

Two consequences follow.

**The documented extension contract is false.** CONTRIBUTING.md says a back end
is "one module in `tools/kbdlayout/generators/` exposing `generate(layout) ->
{path: content}`, plus one entry in `GENERATORS`." Adding a real platform also
requires editing `model.py` (a new `FooTarget`, any new constraints) and
`source.py`, whose `_build()` hardcodes the three targets:

```python
windows = WindowsTarget(**meta["windows"])
linux   = LinuxTarget(**meta["linux"])
macos   = MacosTarget(**meta["macos"])
```

So the advertised one-module change is really a four-file change.

**A Windows limit is enforced for every platform.** `Layout.validate()` rejects
any character above U+FFFF and any dead-key root above U+0FFF, for all targets,
because MSKLC cannot express them. That is a defensible product decision — the
README documents it — but it is currently a *policy* encoded in the layer that
is supposed to hold no policy. If the project ever ships a Linux-only or
macOS-only extension, that decision has to be unpicked from the model rather
than dropped from one back end.

**Suggested change.** Give each back end ownership of its own vocabulary and its
own constraints, and let the model keep only structural rules.

```python
# generators/__init__.py
class Target(Protocol):
    name: str
    def parse_config(self, table: dict) -> object: ...       # was WindowsTarget(**...)
    def constraints(self, layout: Layout) -> list[str]: ...  # was Layout.validate()
    def generate(self, layout: Layout) -> dict[str, str | bytes]: ...

TARGETS: dict[str, Target] = {...}
```

`Layout.validate()` then shrinks to what is genuinely platform-independent:
duplicate key ids, unknown shift states, dead keys declared but not defined (and
the reverse), duplicate bases, and the missing-U+0020 rule. The MSKLC ceilings
move into `windows_klc`, the keysym-collision check into `linux_xkb`, and
`xkb_leader` becomes part of the Linux target's per-dead-key config rather than a
field on the shared `DeadKey`. `source._build()` loops over `TARGETS` instead of
naming three.

This is the change that makes the rest of the extension story true, and it is
the one I would do first.

### P1 — `README.md` is a second source of truth, policed by the largest module in the project

`README.md` is 641 lines, of which **364 are pipe-table rows** restating the
layout. `checks_readme.py` is **638 lines — 25% of all package code** — and its
entire job is to detect when those tables disagree with the TOML.

Every column of those tables except one is mechanically derivable:

| Column | Derivable from the TOML? |
|---|---|
| `Key` (`<kbd>`) | yes — the key's unmodified/Shift character |
| `Char` | yes — the output, or the dead key's default |
| `Unicode` | yes |
| `Character name` | yes — `unicodedata.name()` |
| `**Dead key:**` marker | yes |
| Dead-key `Root` / `Bases` / `Composites` / `Default` | yes |
| **`Description` / `Notes`** | **no — this is hand-written rationale** |

The one non-derivable column is the design rationale, which is the most valuable
prose in the project — and it is the only part of the layout's definition that
does *not* live in the source of truth. The file that holds the reasoning is the
file the architecture treats as untrusted.

The checker is also matching prose with regexes, which is inherently brittle:

```python
pattern = re.compile(r"the (\d+) dead keys")   # checks_readme.py:446
```

Rewording that sentence silently disables the check.

**Suggested change.** Move the rationale into the source and generate the tables.

1. Add `description` to `[[key]]` (per shift state) and `notes` to
   `[[dead_key]]` in the TOML.
2. Add a `docs` generator alongside the existing four, emitting the README
   sections between markers:
   `<!-- generated:keymap AE altgr -->` … `<!-- /generated -->`.
3. `checks_generated` then covers README for free, because README becomes a
   generated file like any other.

What survives in `checks_readme.py` is only what applies to genuinely
hand-written prose — anchors, relative links, stray invisible characters, table
shape — roughly 150 lines. Net: about 500 lines deleted, one whole class of
drift bug eliminated, and the rationale finally lives next to the mapping it
justifies.

The honest trade-off: README becomes partly machine-owned, and contributors must
edit the TOML rather than the table. That is the same bargain the project already
made for the `.klc`, and it went well.

### P1 — Orchestration lives in the CLI, so nothing else can reuse it

`cli.main()` does five things at once: argparse, repository-root discovery,
loading the layout, **choosing and sequencing the checks**, and formatting/exit
codes. Only the fourth is reusable, and it is not reachable.

The test suite therefore re-implements it (`tools/tests/test_checks.py:36`):

```python
def run(root: Path) -> list[str]:
    reporter = Reporter(root)
    layout = source.load(root / LAYOUT_SOURCE)
    checks_generated.check(root, layout, reporter)
    checks_readme.check(root / "README.md", layout, reporter)
    checks_assets.check(root / "assets", layout, reporter)
    checks_repo.check(root, reporter)
    return [f.format_text() for f in reporter.findings]
```

Add a fifth check module to `cli.main()` and **every test in `test_checks.py`
keeps passing without ever running it.** The two copies also already differ: the
real CLI handles a missing `README.md` and a missing `assets/`, the test copy
does not.

There is a second problem in the same place. `cli.py` owns `LAYOUT_SOURCE` and
`find_repository_root`, so four scripts and four test modules import from the CLI
module — library code depending on the command-line layer. `find_repository_root`
also raises `SystemExit` from what is effectively a library function.

**Suggested change.** Mirror what `generators/` already does well:

```python
# checks/__init__.py
CHECKS: dict[str, Callable[[Path, Layout, Reporter], None]] = {
    "generated": checks_generated.check,
    "readme":    checks_readme.check,
    "assets":    checks_assets.check,
    "repo":      checks_repo.check,
}

def run_checks(root: Path, layout: Layout) -> Reporter: ...
```

Move `LAYOUT_SOURCE` and `find_repository_root` into a `project.py` (raising a
`LayoutError` subclass, not `SystemExit`). `cli.main()` becomes argparse plus an
exit code, and the tests call `run_checks` — so a new check is picked up by the
test suite the moment it is registered.

### P2 — The toolchain is not a package

`pyproject.toml` has no `[project]` table, so `kbdlayout` is not installable and
`python -m kbdlayout` fails from the repository root even though `__main__.py`
exists. Instead, four scripts each carry the same preamble:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
```

…in `generate.py`, `validate.py`, `render.py` and `subset_font.py`, plus a fifth
copy in `tests/conftest.py` that is already redundant with
`pythonpath = ["tools"]` in `pyproject.toml`. Each script also re-implements its
own `--root` argument.

`tools/requirements-dev.txt` is a single flat list, so anyone who wants to run
`pytest` also installs `playwright`, `ipykernel`, `nbclient`, `fonttools` and
`brotli`. And two tests **hard-fail rather than skip** when the optional pieces
are absent — in a clean environment with only `pytest` installed:

```
FAILED tools/tests/test_checks.py::test_a_picture_of_the_wrong_size_is_reported
        ModuleNotFoundError: No module named 'PIL'
FAILED tools/tests/test_picture.py::test_the_embedded_font_covers_every_character_drawn
        ModuleNotFoundError: No module named 'fontTools'
```

**Suggested change.**

- Add `[project]` with `package-dir = {"" = "tools"}` and a
  `[project.scripts] kbdlayout = "kbdlayout.cli:main"` entry point.
- Replace `requirements-dev.txt` with extras: `dev` (pytest, ruff, codespell),
  `picture` (pillow, playwright), `font` (fonttools, brotli), `notebook`.
- Collapse the four scripts into subcommands — `kbdlayout generate`, `check`,
  `render`, `subset-font` — with one `--root` defined once. Keep the existing
  script paths as three-line shims so the stdlib-only promise in CONTRIBUTING.md
  still holds and existing instructions keep working.
- Guard the two optional-dependency tests with `pytest.importorskip`.

### P2 — Duplicated primitives across modules

Four cases, each currently kept in step by a comment or a test rather than by
sharing:

| Duplicate | Locations | Risk |
|---|---|---|
| `unicode_name()` + a `_CONTROL_NAMES` table | `model.py:53`, `klc.py:51` | two tables, different types (`dict[int, str]` vs `dict[int, list[str]]`); they can drift |
| `FALLBACK_BASES = tuple(range(0x20, 0x7F))` | `linux_xkb.py:41`, `macos_keylayout.py:51` | both carry a comment saying they must match; nothing enforces it but a test |
| `_XML_ESCAPES` + an escape function | `macos_keylayout.py:124`, `picture.py:302` | **already divergent** — only the macOS copy escapes `"` |
| `DeadKey` dataclass with `mapping`/`default`/`root_char` | `model.py:118`, `klc.py:141` | near-identical shapes maintained separately |

`FALLBACK_BASES` is the interesting one: it is not a platform detail at all. "An
unmapped base yields the root character followed by the base character, on every
platform" is a **cross-platform behavioural contract** — it is what makes Windows,
Linux and macOS agree. It belongs in `model.py`, where that contract is visible,
not duplicated in two back ends with a note asking them to stay equal.

`_XML_ESCAPES` having already diverged is the proof that these do not stay in
step on their own.

### P2 — `checks_repo` is an allowlist that fails open

`checks_repo.py` enforces "ends with exactly one LF, contains no CR" by matching
a fixed list of extensions:

```python
TEXT_GLOBS = ("*.md", "*.json", "*.svg", "*.ipynb", "*.toml",
              "*.txt", "*.yml", "*.yaml", "*.py", ".gitignore")
```

Three of the six generated files have no matching extension and are therefore
**never checked**:

- `dist/linux/symbols/us_intl_sci`
- `dist/linux/us_intl_sci.XCompose`
- `dist/macos/US-International Scientific.keylayout`

`checks_generated` still catches drift in them, so nothing is broken today — but
the hygiene invariant the project states for its text files is not actually
applied to half the files it ships. And because the list is an allowlist, any new
file type added in future is silently exempt: the check fails open.

**Suggested change.** Invert it. Walk `git ls-files`, skip the known-binary set
(`.klc`, `.png`, and anything with a NUL byte in the first 8 KiB), and check
everything else. New files are then covered by default.

### P2 — CI runs eight jobs; two of them duplicate the test suite

| Job | Status |
|---|---|
| `generated` | keep |
| `layout` | keep |
| `tests` (3.11/3.12/3.13) | keep |
| `lint` | keep |
| `picture` | keep |
| `notebook` | keep, but see below |
| `windows-klc` | **duplicate** of `test_klc_is_utf16_with_a_bom_and_crlf` |
| `linux-xkb` | **duplicate** of `test_generated_xkb_compiles_as_cleanly_as_the_stock_us_layout` |

The `windows-klc` job's inline Python asserts exactly the four things that test
asserts — BOM, CRLF present, no bare LF, ends with `ENDKBD`. The `linux-xkb` job
compiles the symbols file with `xkbcomp` and diffs the log against the stock `us`
layout, which is precisely what that test does; and the `tests` job already
`apt-get install`s `x11-xkb-utils xkb-data` so the test is not skipped there.

Keeping the same invariant in two places, in two languages, means fixing it twice
and — worse — being able to change one without noticing the other.

Beyond that, four jobs each re-run checkout, `setup-python` and
`pip install -r tools/requirements-dev.txt`. `generated`, `layout` and `lint` are
all sub-second and share a checkout; they could be steps in one job.

**Suggested change.** Delete `windows-klc` and `linux-xkb` (the tests already
cover them); fold `generated`, `layout` and `lint` into a single `checks` job.
Eight jobs become four. Separately: `notebook` runs `assets/sandbox.ipynb`, which
CONTRIBUTING.md describes as "a scratch pad". Executing it is a fine smoke test,
but it is what drags `ipykernel` and `nbclient` into the dependency list for
everyone — a good candidate for the `notebook` extra above.

### P3 — Output paths and filename derivation

The Windows `.klc` sits at the repository root while every other generated file
lives under `dist/`; there is no `dist/windows/`. The two filenames are also
derived from `layout.name` by two different rules:

```python
windows_klc.py:238   f"{layout.name.replace('-', ' ')}.klc"   -> "US International Scientific.klc"
macos_keylayout.py:291   f"dist/macos/{layout.name}.keylayout" -> "US-International Scientific.keylayout"
```

so the same layout ships under two spellings of its own name. Deriving a shipped
filename by string surgery on a display name is fragile; an explicit
`output_path` in each target's config would say what is actually intended.

The root position of the `.klc` is probably a deliberate compatibility choice —
it is what download links point at, and moving it would break them. If so, that
is worth one comment in the generator saying so, because right now it reads as an
inconsistency rather than a decision.

### P3 — Diagnostics plumbing

Small things in `report.py` and `cli.py` that will bite as the checks grow:

- `Finding.severity` is a bare `str`. `Reporter.errors` filters on
  `== "error"`, so a typo in a `severity=` argument silently downgrades a
  finding to a warning. A `Literal["error", "warning"]` or an enum costs nothing.
- Findings go to **stdout**, the summary line and load errors to **stderr**. Any
  consumer piping the output gets half the story.
- `IN_GITHUB_ACTIONS` is read at **import time** (`report.py:11`), so the
  GitHub-annotation formatting path cannot be exercised by a test without
  reimporting the module — which is why it currently has no test. A
  `--format text|json|github` flag would be both testable and more useful.
- `Reporter.add()` falls back to an absolute path when `relative_to` raises,
  silently producing machine-unfriendly output rather than saying so.

### P3 — Model lookups are linear scans

`Layout.key()`, `Layout.dead_key()` and `Layout.key_producing()` are all
`for … in …: if … return`. Instrumenting a full generation run:

```
Layout.key()      called 792 times over 50 keys
Layout.dead_key() called 196 times over 28 dead keys
≈ 45,000 comparisons per run
```

Full generation measures **0.096 s**, so this is not a performance problem and I
would not treat it as one. It is listed because it is a shape that only works at
this size: anything that generates many layouts, or a future dead key with a
large map, turns it quadratic. The fix is cheap when it is wanted — build
`_by_id` / `_by_root` dicts once after loading — but it needs `Layout` and `Key`
to stop being mutable first, so it is not free today.

### P3 — Test-suite gaps

The suite is strong where it exists (100 tests, differential checks across three
platforms, a `.klc` round-trip through an independent parser). The gaps are at
the edges:

- **`tools/generate.py` has no test at all.** It is the primary developer entry
  point and it contains real logic: stale detection, the `--check` exit code, the
  created/updated/unchanged distinction. Nothing exercises it.
- **`cli.main()` has no test** — neither exit codes nor `--strict`.
- Two tests hard-fail rather than skip without optional dependencies (above).
- `conftest.py`'s `sys.path.insert` is redundant with `pythonpath = ["tools"]`
  (verified: the suite passes with it removed).

## Suggested target structure

```
pyproject.toml                 [project] + extras + entry point
tools/kbdlayout/
    project.py                 LAYOUT_SOURCE, find_repository_root   (was in cli.py)
    model.py                   structural validation only; FALLBACK_BASES
    unicode_names.py           the one unicode_name() + control-name table
    source.py                  loops over TARGETS instead of naming three
    keys.py, keysyms.py, markdown.py, klc.py, report.py
    generators/
        __init__.py            Target protocol; TARGETS registry
        windows_klc.py         + MSKLC code-point ceilings
        linux_xkb.py           + xkb_leader config and keysym-collision check
        macos_keylayout.py
        picture.py
        docs.py                NEW — generates the README tables
    checks/
        __init__.py            CHECKS registry + run_checks()
        generated.py, assets.py, repo.py
        readme.py              ~150 lines: anchors, links, stray chars, shape
    cli.py                     argparse + exit codes only
```

## Where I would start

Ordered by value per unit of disruption:

1. **Extract `run_checks()` and `project.py`** (P1, small). Removes the
   duplicated orchestration in the tests immediately, and everything else gets
   easier afterwards.
2. **Add `[project]` and extras** (P2, small). Makes `python -m kbdlayout` work,
   deletes five `sys.path` hacks, and unblocks the CLI consolidation.
3. **Delete the two duplicated CI jobs, merge three more** (P2, small). Pure
   subtraction. The win is one invariant in one place, not speed — the whole
   suite already finishes in about 45 seconds of wall clock.
4. **Introduce the `Target` protocol and move the platform constraints out of
   `model.py`** (P1, medium). Makes the documented extension contract true.
5. **Generate the README tables** (P1, large). The biggest win and the biggest
   change; it needs the rationale prose moved into the TOML first, which is a
   mechanical but careful edit across 50 keys and 28 dead keys. Worth doing after
   4, so the docs generator can be a `Target` like the rest.

Items 5 and 4 together remove roughly 500 lines of checking code and one entire
category of bug. Items 1–3 are an afternoon and make the codebase easier to work
on regardless of whether 4 and 5 ever happen.

## Appendix: how this was verified

```sh
python3 tools/validate.py            # 50 keys, 28 dead keys, 0 errors, 0 warnings
python3 tools/generate.py --check    # all six generated files unchanged
time python3 tools/generate.py --check   # 0.096 s

python3 -m kbdlayout                 # No module named kbdlayout  (packaging)
grep -c '\[project\]' pyproject.toml # 0

# Duplication
grep -rn 'def unicode_name' tools/            # model.py:53, klc.py:51
grep -rn 'FALLBACK_BASES' tools/              # linux_xkb.py:41, macos_keylayout.py:51
grep -rn '_XML_ESCAPES\s*=' tools/            # macos:124 (with &quot;), picture:302 (without)
grep -rn 'sys.path.insert' tools/             # 5 copies

# checks_repo coverage — 50 files, none of the three dist/ text files
python3 -c "import sys;sys.path.insert(0,'tools');
from pathlib import Path;from kbdlayout.checks_repo import iter_text_files;
print(len(list(iter_text_files(Path.cwd()))))"

# README composition
wc -l README.md                               # 641
awk '/^\|/{n++} END{print n}' README.md       # 364 table rows
wc -l tools/kbdlayout/checks_readme.py        # 638

# Lookup call counts: Layout.key/dead_key wrapped with a counter across render_all()
#   -> 792 and 196 calls, ~45,000 comparisons

# conftest sys.path hack is redundant with pythonpath = ["tools"]
#   -> suite passes with the insert removed
```
