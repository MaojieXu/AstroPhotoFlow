"""Export current authored files, real definitions, imports and static callers."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / '.artifacts/bundles/AstroPhotoFlow-Siril'
SUFFIXES = {'.py', '.ts', '.tsx', '.vue', '.js', '.mjs', '.ps1', '.json', '.toml', '.yml', '.yaml'}


def python_symbols(path: Path, module: str) -> dict:
    source = path.read_text(encoding='utf-8-sig')
    tree = ast.parse(source)
    imports = []
    functions = []
    package = module if path.name == '__init__.py' else module.rpartition('.')[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend({'module': alias.name, 'names': []} for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = importlib.util.resolve_name('.' * node.level + (node.module or ''), package) if node.level else node.module
            imports.append({'module': name, 'names': [alias.name for alias in node.names]})

    def definitions(nodes, parent=''):
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = parent + node.name
                calls = sorted({ast.unparse(child.func) for child in ast.walk(node) if isinstance(child, ast.Call)})
                functions.append({'name': name, 'line': node.lineno, 'end_line': node.end_lineno,
                    'parameters': ast.unparse(node.args),
                    'returns': ast.unparse(node.returns) if node.returns else None,
                    'calls': calls})
                definitions(node.body, name + '.')
            elif isinstance(node, ast.ClassDef):
                definitions(node.body, parent + node.name + '.')
            elif isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Lambda):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                binding = next((target.id for target in targets if isinstance(target, ast.Name)), f'<lambda@{node.lineno}>')
                value = node.value
                functions.append({'name': parent + binding, 'line': value.lineno, 'end_line': value.end_lineno,
                    'parameters': ast.unparse(value.args), 'returns': None, 'definition_kind': 'lambda',
                    'calls': sorted({ast.unparse(child.func) for child in ast.walk(value) if isinstance(child, ast.Call)})})
                definitions(ast.iter_child_nodes(value), parent + binding + '.')
            elif isinstance(node, ast.Lambda):
                name = parent + f'<lambda@{node.lineno}:{node.col_offset}>'
                functions.append({'name': name, 'line': node.lineno, 'end_line': node.end_lineno,
                    'parameters': ast.unparse(node.args), 'returns': None, 'definition_kind': 'lambda',
                    'calls': sorted({ast.unparse(child.func) for child in ast.walk(node) if isinstance(child, ast.Call)})})
                definitions(ast.iter_child_nodes(node), name + '.')
            else:
                definitions(ast.iter_child_nodes(node), parent)

    definitions(tree.body)
    return {'imports': imports, 'functions': functions}


def source_files() -> dict[str, Path]:
    roots = ['src/astrophotoflow', 'scripts', 'tests', '.github/workflows', 'frontend/packages/astrophotoflow-ui',
             'frontend/src/platform/astrophotoflow']
    files = {}
    for scope in roots:
        for path in (ROOT / scope).rglob('*'):
            if path.is_file() and path.suffix in SUFFIXES and not {'node_modules', '__pycache__', '.pytest_cache'} & set(path.parts):
                files[path.relative_to(ROOT).as_posix()] = path
    # This authored compiler helper is outside the UI/native roots and is new to Git.
    compiler_helper = ROOT / 'frontend/scripts/export_source_inventory.mjs'
    files[compiler_helper.relative_to(ROOT).as_posix()] = compiler_helper
    # Include only modified native-host integration files, not the whole upstream.
    changed = subprocess.check_output(['git', '-c', 'safe.directory=' + str(ROOT), 'diff', '--name-only', 'HEAD', '--', 'frontend', 'engine'], cwd=ROOT, text=True)
    for name in changed.splitlines():
        path = ROOT / name
        if path.is_file() and path.suffix in SUFFIXES:
            files[name] = path
    for scope in ['adapter', 'tools', 'tests', 'operations', 'nodes', 'locales']:
        for path in (BUNDLE / scope).rglob('*'):
            if path.is_file() and path.suffix in SUFFIXES and '__pycache__' not in path.parts:
                files['bundle:' + path.relative_to(BUNDLE).as_posix()] = path
    for name in ['bundle.json', 'development.json']:
        files['bundle:' + name] = BUNDLE / name
    baseline = (ROOT / 'docs/development/file-refactoring-plan.md').read_text(encoding='utf-8')
    for heading in re.findall(r'<summary>(.*?)</summary>', baseline):
        name = heading.split(' — ')[0]
        path = BUNDLE / name.removeprefix('bundle:') if name.startswith('bundle:') else ROOT / name
        if path.is_file():
            files.setdefault(name, path)
    return files


def powershell_symbols(paths: list[Path]) -> dict:
    if not paths:
        return {}
    script = r'''
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$inventoryPaths = ConvertFrom-Json ([Console]::In.ReadToEnd())
$inventoryResult = @{}
foreach ($inventoryPath in $inventoryPaths) {
    $inventoryTokens = $null
    $inventoryErrors = $null
    $inventoryAst = [System.Management.Automation.Language.Parser]::ParseFile($inventoryPath, [ref]$inventoryTokens, [ref]$inventoryErrors)
    if ($inventoryErrors.Count) { throw "Cannot parse $inventoryPath" }
    $inventoryFunctions = @($inventoryAst.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst]}, $true) | ForEach-Object {
        $inventoryParameters = @($_.Parameters)
        if ($_.Body.ParamBlock) { $inventoryParameters += @($_.Body.ParamBlock.Parameters) }
        $inventoryCalls = @($_.Body.FindAll({param($node) $node -is [System.Management.Automation.Language.CommandAst]}, $true) | ForEach-Object { $_.GetCommandName() } | Where-Object { $_ } | Sort-Object -Unique)
        @{name=$_.Name; line=$_.Extent.StartLineNumber; parameters=@($inventoryParameters | ForEach-Object {$_.Extent.Text}); returns=$null; calls=$inventoryCalls}
    })
    $inventoryResult[$inventoryPath] = @{imports=@(); functions=$inventoryFunctions}
}
$inventoryResult | ConvertTo-Json -Depth 12 -Compress
'''
    result = subprocess.run(['powershell', '-NoProfile', '-Command', script],
        input=json.dumps([str(path) for path in paths]), capture_output=True, text=True,
        encoding='utf-8', check=True, timeout=30)
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/development/source-inventory.json')
    args = parser.parse_args()
    files = source_files()
    generated = lambda name: '/generated/' in name or name.endswith('/cli/generated.py') or name in {'docs/api/openapi.json', 'uv.lock', 'frontend/pnpm-lock.yaml'} or name.startswith(('bundle:operations/', 'bundle:nodes/', 'bundle:locales/', 'src/astrophotoflow/vendor/'))
    frontend = [str(path) for name, path in files.items() if path.suffix in {'.ts', '.tsx', '.vue', '.js', '.mjs'} and not generated(name)]
    node = ROOT / '.artifacts/toolchains/node-v26.8.2-win-x64/node.exe'
    compiler = subprocess.run([str(node), str(ROOT / 'frontend/scripts/export_source_inventory.mjs')],
        input=json.dumps(frontend), capture_output=True, text=True, encoding='utf-8', check=True, timeout=60)
    frontend_symbols = json.loads(compiler.stdout)
    shell_symbols = powershell_symbols([path for path in files.values() if path.suffix == '.ps1'])
    modules = {}
    for name, path in files.items():
        if path.suffix == '.py':
            module = name.removeprefix('src/').removeprefix('bundle:').removesuffix('.py').replace('/', '.')
            modules[module.removesuffix('.__init__')] = name
    entries = {}
    for name, path in sorted(files.items()):
        auto = generated(name)
        symbols = {'imports': [], 'functions': []}
        if path.suffix == '.py' and not auto:
            module = name.removeprefix('src/').removeprefix('bundle:').removesuffix('.py').replace('/', '.').removesuffix('.__init__')
            symbols = python_symbols(path, module)
        elif str(path) in frontend_symbols:
            symbols = frontend_symbols[str(path)]
        elif str(path) in shell_symbols:
            symbols = shell_symbols[str(path)]
        dependencies = set()
        for item in symbols['imports']:
            target = modules.get(item['module'])
            if target:
                dependencies.add(target)
            for member in item.get('names', []):
                if target := modules.get(item['module'] + '.' + member):
                    dependencies.add(target)
            if not name.startswith('bundle:') and path.suffix in {'.ts', '.tsx', '.vue', '.js', '.mjs'}:
                value = item['module']
                base = path.parent / value if value.startswith('.') else ROOT / ('frontend/src/' + value[2:]) if value.startswith('@/') else ROOT / ('frontend/packages/astrophotoflow-ui/src/' + value[4:]) if value.startswith('@ui/') else ROOT / 'frontend/packages/astrophotoflow-ui/src/index' if value == '@astrophotoflow/ui' else None
                if base is not None:
                    for candidate in [base, *[Path(str(base) + suffix) for suffix in ['.ts', '.vue', '.mjs', '/index.ts']]]:
                        if candidate.is_file():
                            relative = candidate.resolve().relative_to(ROOT).as_posix()
                            if relative in files:
                                dependencies.add(relative)
                            break
        entries[name] = {'disposition': '生成' if auto else '当前源码', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'lines': len(path.read_text(encoding='utf-8-sig').splitlines()), **symbols,
            'dependencies': sorted(dependencies), 'importing_callers': [], 'direct_importing_tests': []}
    for name, entry in entries.items():
        for dependency in entry['dependencies']:
            entries[dependency]['importing_callers'].append(name)
            if '/tests/' in '/' + name or name.endswith('.test.ts'):
                entries[dependency]['direct_importing_tests'].append(name)
    baseline = Path(ROOT / 'docs/development/file-refactoring-plan.md').read_text(encoding='utf-8')
    prior = []
    origins = {}
    transitions = json.loads((ROOT / 'docs/development/file-refactoring-transitions.json').read_text(encoding='utf-8'))
    file_resolutions = {item['source']: item for item in transitions['file_resolutions']}
    for heading, body in re.findall(r'<details>\s*<summary>(.*?)</summary>(.*?)</details>', baseline, re.DOTALL):
        name = heading.split(' — ')[0]
        target_line = next((line for line in body.splitlines() if line.startswith('目标：')), '')
        targets = re.findall(r'`([^`]+)`', target_line)
        if name.startswith('bundle:'):
            targets = ['bundle:' + target for target in targets]
        resolution = file_resolutions.get(name)
        if resolution is not None:
            targets = resolution['targets']
        resolved = {target: [path for path in entries if path == target.rstrip('/') or path.startswith(target.rstrip('/') + '/')] for target in targets}
        for paths in resolved.values():
            for target in paths:
                origins.setdefault(target, []).append(name)
        prior.append({'source': name, 'planned_disposition': heading.split(' — ')[1],
            'current_source_exists': name in entries, 'declared_target_paths': targets,
            'current_declared_target_paths': [target for target, paths in resolved.items() if paths],
            'resolved_target_files': sorted({path for paths in resolved.values() for path in paths}),
            'unresolved_target_paths': [target for target, paths in resolved.items() if not paths],
            'resolution': resolution})
    prior_by_name = {item['source']: item for item in prior}
    for name, entry in entries.items():
        source_paths = sorted(set(origins.get(name, [])))
        if name in prior_by_name:
            source_paths = sorted({*source_paths, name})
        entry['baseline_sources'] = source_paths
        if entry['disposition'] != '生成':
            planned = prior_by_name.get(name, {}).get('planned_disposition')
            entry['disposition'] = '合并' if len(source_paths) > 1 else '拆分' if planned == '拆分' or source_paths and source_paths != [name] else '保留'
        entry['new_file'] = name not in prior_by_name
    for item in prior:
        item['current_disposition'] = entries[item['source']]['disposition'] if item['current_source_exists'] else '拆分' if item['resolved_target_files'] else '删除'
    result = {'schema_version': 1, 'scope': 'Current authored platform/Bundle code, tests and generated declarations; excludes upstream engine except changed integration, Bundle binaries and official documentation.',
        'limits': 'Imports/call expressions are static evidence, not a runtime call graph or proof of test execution. Missing return annotations remain null; no inferred contract is authored here.',
        'files': entries, 'baseline_files': prior, 'transition_resolutions': transitions,
        'summary': {'files': len(entries), 'functions': sum(len(entry['functions']) for entry in entries.values()), 'baseline_files': len(prior)}}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result['summary']))


if __name__ == '__main__':
    main()
