"""The sandbox notebook is source too, and it calls into the package.

Nothing but CI used to notice when it stopped working, and CI only noticed by
executing every cell, which needs the notebook extra installed. Renaming a
module or changing a signature would break it silently for anyone else.

These tests read the notebook and resolve what it imports, using nothing but
the standard library, so a move like ``checks_generated`` -> ``build`` fails
here rather than three jobs later.
"""

import ast
import importlib
import inspect
import json

import pytest

NOTEBOOK = "assets/sandbox.ipynb"


@pytest.fixture(scope="module")
def cells(repo_root) -> list[str]:
    notebook = json.loads((repo_root / NOTEBOOK).read_text(encoding="utf-8"))
    return ["".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"]


def test_every_cell_parses(cells):
    for source in cells:
        ast.parse(source)


def _imports(cells: list[str]) -> list[tuple[str, str | None]]:
    """Every ``kbdlayout`` module the notebook imports, with the name it takes."""
    found: list[tuple[str, str | None]] = []
    for source in cells:
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("kbdlayout"):
                found.extend((node.module, alias.name) for alias in node.names)
            elif isinstance(node, ast.Import):
                found.extend(
                    (alias.name, None) for alias in node.names if alias.name.startswith("kbdlayout")
                )
    return found


def test_the_notebook_imports_something(cells):
    assert _imports(cells), "expected the notebook to use the package"


def test_every_imported_name_still_exists(cells):
    for module_name, attribute in _imports(cells):
        module = importlib.import_module(module_name)
        if attribute is not None:
            assert hasattr(module, attribute), (
                f"{NOTEBOOK} imports {attribute!r} from {module_name}, which no longer has it"
            )


def test_every_call_into_the_package_matches_its_signature(cells):
    """Catches a changed signature, not just a moved name."""
    imported = {
        attribute: getattr(importlib.import_module(module), attribute)
        for module, attribute in _imports(cells)
        if attribute is not None
    }
    checked = 0
    for source in cells:
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            target = imported.get(node.func.id)
            if target is None or not callable(target):
                continue
            signature = inspect.signature(target)
            try:
                signature.bind(*[None] * len(node.args), **{k.arg: None for k in node.keywords})
            except TypeError as error:
                pytest.fail(
                    f"{NOTEBOOK} calls {node.func.id}() with {len(node.args)} argument(s), "
                    f"but its signature is {signature}: {error}"
                )
            checked += 1
    assert checked, "expected the notebook to call into the package"
