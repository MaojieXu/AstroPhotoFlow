import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

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
    for path in (PACKAGE / "contracts").rglob("*.py"):
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
                assert name == "astrophotoflow.modules.data.public", (path, name)


def test_data_does_not_import_transport_or_other_business_modules():
    for path in (PACKAGE / "modules/data").rglob("*.py"):
        for name in imports(path):
            assert not name.startswith("astrophotoflow.interfaces"), (path, name)
            if name.startswith("astrophotoflow.modules"):
                assert name.startswith("astrophotoflow.modules.data"), (path, name)


def test_nodes_do_not_import_workflows_or_transport():
    for path in (PACKAGE / "modules/nodes").rglob("*.py"):
        for name in imports(path):
            assert not name.startswith(("astrophotoflow.modules.workflows", "astrophotoflow.interfaces")), (path, name)
            if name.startswith("astrophotoflow.modules"):
                assert name.startswith(("astrophotoflow.modules.nodes", "astrophotoflow.modules.software.public")), (path, name)


def test_software_has_no_http_framework_or_adapter_dependency():
    for path in (PACKAGE / "modules/software").rglob("*.py"):
        for name in imports(path):
            assert not name.startswith(("fastapi", "starlette", "astrophotoflow.interfaces")), (path, name)


def test_refactored_data_capabilities_have_no_http_framework_dependency():
    for owner in ("data", "nodes"):
        for path in (PACKAGE / "modules" / owner).rglob("*.py"):
            for name in imports(path):
                assert not name.startswith(("fastapi", "starlette", "astrophotoflow.interfaces")), (path, name)


def test_public_business_entries_import_without_http_and_nodes_import_in_either_order():
    for order in [("public", "catalog"), ("catalog", "public")]:
        subprocess.run([sys.executable, "-c", (
            "import importlib,sys; "
            f"[importlib.import_module('astrophotoflow.modules.nodes.'+name) for name in {order!r}]; "
            "import astrophotoflow.modules.data.public; "
            "assert 'fastapi' not in sys.modules and 'starlette' not in sys.modules"
        )], check=True, cwd=ROOT)


def test_data_services_import_without_loading_transport_frameworks():
    subprocess.run([sys.executable, "-c", (
        "import sys; "
        "import astrophotoflow.modules.data.activity; "
        "import astrophotoflow.modules.data.assets.service; "
        "import astrophotoflow.modules.data.assets.canvas; "
        "import astrophotoflow.modules.data.assets.queries; "
        "import astrophotoflow.modules.data.library.queries; "
        "import astrophotoflow.modules.data.datasets.service; "
        "import astrophotoflow.modules.data.projects.service; "
        "import astrophotoflow.modules.data.projects.references; "
        "import astrophotoflow.modules.data.media.previews; "
        "import astrophotoflow.modules.data.imports.submission; "
        "import astrophotoflow.modules.data.imports.uploads; "
        "import astrophotoflow.modules.data.imports.tasks; "
        "import astrophotoflow.modules.data.imports.sources; "
        "import astrophotoflow.modules.data.trash.service; "
        "import astrophotoflow.modules.data.trash.cleanup; "
        "assert 'fastapi' not in sys.modules and 'starlette' not in sys.modules"
    )], check=True, timeout=20)


def test_module_functions_do_not_silently_override_another_definition():
    for path in PACKAGE.rglob("*.py"):
        names = set()
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(isinstance(decorator, ast.Name) and decorator.id == "overload" or
                   isinstance(decorator, ast.Attribute) and decorator.attr == "overload" for decorator in node.decorator_list):
                continue
            assert node.name not in names, (path, node.name)
            names.add(node.name)


def test_public_entries_are_explicit_exports_without_business_implementation():
    for relative in ("modules/data/public.py", "modules/software/public.py", "modules/software/bundles/__init__.py", "core/workbench/__init__.py"):
        path = PACKAGE / relative
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                assert all(alias.name != "*" for alias in node.names)
            elif isinstance(node, ast.Assign):
                assert [target.id for target in node.targets if isinstance(target, ast.Name)] == ["__all__"]
            else:
                assert isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str), (path, node.lineno)

def test_native_workflow_authority_has_no_platform_workflows_business_module():
    assert not (PACKAGE / 'modules/workflows').exists()



def test_format_codecs_do_not_depend_on_import_services_orm_or_http():
    prefix = 'astrophotoflow.modules.data.'
    for path in (PACKAGE / 'modules/data/formats').glob('*.py'):
        for dependency in imports(path):
            if dependency.startswith(prefix):
                assert dependency.startswith(prefix + 'formats'), (path, dependency)
            assert not dependency.startswith(('sqlalchemy', 'fastapi', 'starlette')), (path, dependency)



def test_import_stages_do_not_depend_back_on_runner_or_batch_completion():
    prefix = 'astrophotoflow.modules.data.imports.'
    for name in ('pipeline', 'stages', 'metadata', 'enumeration', 'progress', 'tasks'):
        path = PACKAGE / 'modules/data/imports' / (name + '.py')
        assert not any(dependency in {prefix + 'runner', prefix + 'batches'} for dependency in imports(path)), path
