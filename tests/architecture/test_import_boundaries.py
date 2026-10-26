import ast
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src/astrophotoflow"


def imports(path):
    relative = path.relative_to(ROOT / "src").with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
        parent = ".".join(parts)
    else:
        parent = ".".join(parts[:-1])
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            yield importlib.util.resolve_name("." * node.level + (node.module or ""), parent) if node.level else node.module


def test_contracts_only_depend_on_standard_library_pydantic_and_contracts():
    for path in (PACKAGE / "contracts").glob("*.py"):
        for name in imports(path):
            assert name.split(".")[0] in sys.stdlib_module_names | {"pydantic"} or name.startswith("astrophotoflow.contracts"), (path, name)


def test_core_has_no_business_or_transport_imports_except_migration_assembly():
    assembly = PACKAGE / "core/database/alembic/env.py"
    for path in (PACKAGE / "core").rglob("*.py"):
        for name in imports(path):
            if path == assembly:
                assert not name.startswith("astrophotoflow.interfaces"), (path, name)
            else:
                assert not name.startswith(("astrophotoflow.modules", "astrophotoflow.interfaces")), (path, name)


def test_client_cli_and_mcp_do_not_access_business_models_or_database():
    paths = [PACKAGE / "client.py"]
    for area in ("client", "cli", "mcp"):
        paths.extend((PACKAGE / "interfaces" / area).rglob("*.py"))
    for path in paths:
        for name in imports(path):
            assert not name.startswith(("sqlalchemy", "sqlite3", "astrophotoflow.modules", "astrophotoflow.core.database")), (path, name)


def test_data_consumers_use_public_entries_except_migration_metadata():
    for path in PACKAGE.rglob("*.py"):
        if path.is_relative_to(PACKAGE / "modules/data") or path == PACKAGE / "core/database/alembic/env.py":
            continue
        for name in imports(path):
            if name.startswith("astrophotoflow.modules.data"):
                assert name in {"astrophotoflow.modules.data.public", "astrophotoflow.modules.data.routes"}, (path, name)


def test_data_does_not_import_transport_or_other_business_modules():
    for path in (PACKAGE / "modules/data").glob("*.py"):
        for name in imports(path):
            assert not name.startswith("astrophotoflow.interfaces"), (path, name)
            if name.startswith("astrophotoflow.modules"):
                assert name.startswith("astrophotoflow.modules.data"), (path, name)
