"""Guard: everything the production image imports must be a runtime dependency (not dev-only)."""
import ast
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# import name -> distribution name where they differ
DIST_ALIASES = {"starlette": "fastapi", "jwt": "pyjwt", "dotenv": "python-dotenv", "argon2": "argon2-cffi", "yaml": "pyyaml", "PIL": "pillow"}


def _runtime_dependencies() -> set[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    return {re.split(r"[<>=!~\[ ;]", dep, maxsplit=1)[0].lower().replace("_", "-") for dep in project["dependencies"]}


def test_app_imports_are_runtime_dependencies() -> None:
    stdlib = set(sys.stdlib_module_names)
    declared = _runtime_dependencies()
    missing: dict[str, str] = {}
    for path in sorted((ROOT / "app").rglob("*.py")) + sorted((ROOT / "migrations").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in stdlib or name in {"app", "migrations", "__future__"}:
                    continue
                dist = DIST_ALIASES.get(name, name).lower().replace("_", "-")
                if dist not in declared:
                    missing[name] = str(path.relative_to(ROOT))
    assert not missing, f"imported but not in [project].dependencies: {missing}"
