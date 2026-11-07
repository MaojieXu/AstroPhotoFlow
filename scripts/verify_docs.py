"""文档门禁：预算、双语配对、一行一段、链接、Agent Notes 与 Skills。

用法::

    python scripts/verify_docs.py all
    python scripts/verify_docs.py budgets
    python scripts/verify_docs.py pairing --list
    python scripts/verify_docs.py pairing --write docs/architecture.md
    python scripts/verify_docs.py pairing --write-all

规则见 ``docs/AGENTS.md``，双语契约见 ``docs/i18n/README.md``。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

import doc_pairing as dp

BUDGET_MANIFEST = 'scripts/doc-budgets.json'
PAIRS_MANIFEST = 'scripts/doc-pairs.json'
LINK_EXCEPTIONS = 'scripts/doc-link-exceptions.json'
NOTES_DIR = '.agents/notes'
SKILLS_DIR = '.agents/skills'
SKILL_MAX_SIZE = 8000
SKILL_DESCRIPTION_MAX = 500
SKILL_NAME_RE = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
NOTE_FILENAME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md$')
NOTE_CLASSES = ('feature', 'bug-fix', 'simplification', 'architecture', 'process', 'testing')
NOTE_LIFECYCLES = ('implemented', 'archived')
NOTE_SECTIONS = ('Problem', 'Decision', 'Alternatives considered', 'Consequences')
ANCHOR_RE = re.compile(r'<a\s+(?:id|name)="([^"]+)"')
SKIP_SCHEME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*:')
WALK_EXCLUDED = {'.git', '.venv', 'node_modules', '.artifacts', 'reference', 'engine'}
ROOT_FILES = ('README.md', 'README.en.md', 'CONTRIBUTING.md', 'CONTRIBUTING.en.md', 'AGENTS.md')
MD_TREES = ('docs', '.agents', 'src', 'frontend/packages/astrophotoflow-ui', 'frontend/src/platform/astrophotoflow')


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    message: str
    line: int | None = None

    def __str__(self) -> str:
        location = self.path if self.line is None else f'{self.path}:{self.line}'
        return f'[{self.rule}] {location} {self.message}'


def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8').replace('\r\n', '\n').replace('\r', '\n')


def measure(text: str) -> int:
    """Non-whitespace character count, the unit used by every budget."""
    return len(re.sub(r'\s+', '', text))


def rel_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def load_json(path: Path) -> tuple[object | None, list[str]]:
    if not path.is_file():
        return None, [f'清单不存在：{path.name}']
    try:
        return json.loads(read_text(path)), []
    except json.JSONDecodeError as error:
        return None, [f'清单不是合法 JSON：{error}']


def is_excluded(rel: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if pattern.endswith('/**'):
            prefix = pattern[:-3]
            if rel == prefix or rel.startswith(prefix + '/'):
                return True
        elif pattern.startswith('**/') and pattern.endswith('/**'):
            if f'/{pattern[3:-3]}/' in f'/{rel}/':
                return True
        elif rel == pattern:
            return True
    return False


def walk_markdown(root: Path, base: str) -> list[Path]:
    start = root / base
    if not start.is_dir():
        return []
    found: list[Path] = []
    for current, directories, files in os.walk(start):
        directories[:] = sorted(name for name in directories if name not in WALK_EXCLUDED)
        for name in sorted(files):
            if name.endswith('.md'):
                found.append(Path(current, name))
    return found


def all_markdown_sources(root: Path) -> list[Path]:
    sources: list[Path] = []
    for name in ROOT_FILES:
        candidate = root / name
        if candidate.is_file():
            sources.append(candidate)
    for base in MD_TREES:
        sources.extend(walk_markdown(root, base))
    unique: list[Path] = []
    seen: set[str] = set()
    for source in sources:
        key = rel_posix(source, root)
        if key not in seen:
            seen.add(key)
            unique.append(source)
    return unique


def en_path(rel: str) -> str:
    return Path(rel).with_suffix('').as_posix() + '.en.md'


def check_budgets(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    data, errors = load_json(root / BUDGET_MANIFEST)
    findings.extend(Finding('budgets', BUDGET_MANIFEST, message) for message in errors)
    if not isinstance(data, dict):
        return findings
    files = data.get('files', {})
    if not isinstance(files, dict):
        return findings + [Finding('budgets', BUDGET_MANIFEST, 'files 必须是对象')]
    for rel, limit in files.items():
        if isinstance(limit, dict):
            pairs = (('zh', rel), ('en', en_path(rel)))
            for locale, path_name in pairs:
                value = limit.get(locale)
                if not isinstance(value, int) or value <= 0:
                    findings.append(Finding('budgets', BUDGET_MANIFEST, f'{rel} 的 {locale} 上限必须是正整数'))
                    continue
                findings.extend(check_one_budget(root, path_name, value))
        elif isinstance(limit, int) and limit > 0:
            findings.extend(check_one_budget(root, rel, limit))
        else:
            findings.append(Finding('budgets', BUDGET_MANIFEST, f'{rel} 的上限必须是正整数或 {{zh,en}}'))
    agents = data.get('agents_md', {})
    default = agents.get('default', 4000)
    overrides = agents.get('overrides', {})
    for path in walk_agents_md(root, agents.get('exclude', [])):
        rel = rel_posix(path, root)
        limit = overrides.get(rel, default)
        if not isinstance(limit, int) or limit <= 0:
            findings.append(Finding('budgets', rel, 'AGENTS.md 上限必须是正整数'))
            continue
        findings.extend(check_one_budget(root, rel, limit))
    return findings


def walk_agents_md(root: Path, extra_exclude: list[str]) -> list[Path]:
    found: list[Path] = []
    for current, directories, files in os.walk(root):
        directories[:] = sorted(
            name for name in directories if name not in WALK_EXCLUDED and name != '.dsh'
        )
        for name in sorted(files):
            if name == 'AGENTS.md':
                path = Path(current, name)
                rel = rel_posix(path, root)
                if not is_excluded(rel, extra_exclude) and not is_excluded(rel, ['frontend/AGENTS.md']):
                    found.append(path)
    return found


def check_one_budget(root: Path, rel: str, limit: int) -> list[Finding]:
    path = root / rel
    if not path.is_file():
        return [Finding('budgets', rel, '清单登记的文档不存在')]
    size = measure(read_text(path))
    if size > limit:
        return [Finding('budgets', rel, f'超出预算（{size} > {limit} 非空白字符）')]
    return []


def mask_fences(text: str) -> str:
    lines = text.split('\n')
    masked: list[str] = []
    marker: str | None = None
    for line in lines:
        fence = dp.FENCE_RE.match(line)
        if marker is None and fence:
            marker = fence.group(2)
            masked.append(' ' * len(line))
            continue
        if marker is not None:
            if fence and fence.group(2)[0] == marker[0] and len(fence.group(2)) >= len(marker):
                marker = None
            masked.append(' ' * len(line))
            continue
        masked.append(line)
    return '\n'.join(masked)


def check_wrap(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for source in all_markdown_sources(root):
        rel = rel_posix(source, root)
        text = mask_fences(read_text(source))
        for line_number in wrapped_paragraphs(text):
            findings.append(Finding('wrap', rel, '段落跨多个物理行（一段一行）', line_number))
    return findings


def wrapped_paragraphs(text: str) -> list[int]:
    """Return start lines of prose units that span more than one physical line."""
    lines = text.split('\n')
    violations: list[int] = []
    unit: list[str] = []
    start = 0
    index = 0

    if lines and lines[0].strip() == '---':
        for offset, line in enumerate(lines[1:], 2):
            if line.strip() in ('---', '...'):
                index = offset
                break

    def flush() -> None:
        nonlocal unit
        if len(unit) > 1:
            violations.append(start)
        unit = []

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            flush()
            index += 1
            continue
        fence = dp.FENCE_RE.match(line)
        if fence:
            flush()
            index += 1
            while index < len(lines) and not (
                dp.FENCE_RE.match(lines[index])
                and dp.FENCE_RE.match(lines[index]).group(2)[0] == fence.group(2)[0]
                and len(dp.FENCE_RE.match(lines[index]).group(2)) >= len(fence.group(2))
            ):
                index += 1
            index += 1
            continue
        if dp.THEMATIC_RE.match(line) or dp.HEADING_RE.match(line) or dp.TABLE_RE.match(line):
            flush()
            index += 1
            continue
        if stripped.startswith('<'):
            flush()
            index += 1
            continue
        marker = dp.LIST_RE.match(line)
        if marker:
            flush()
            unit = [line]
            start = index + 1
            index += 1
            continue
        quote = dp.QUOTE_RE.match(line)
        if quote:
            if not line.lstrip()[1:].strip():
                flush()
                index += 1
                continue
            if not unit:
                start = index + 1
                unit = []
            unit.append(line)
            index += 1
            continue
        if not unit:
            start = index + 1
        unit.append(line)
        index += 1

    flush()
    return violations


def collect_anchors(text: str) -> set[str]:
    anchors = {match.group(1) for match in ANCHOR_RE.finditer(text)}
    seen: dict[str, int] = {}
    for line in text.split('\n'):
        heading = dp.HEADING_RE.match(line)
        if not heading:
            continue
        slug = dp.slugify(heading.group(2))
        count = seen.get(slug, 0)
        anchors.add(slug if count == 0 else f'{slug}-{count}')
        seen[slug] = count + 1
    return anchors


def line_links(text: str) -> list[tuple[int, str]]:
    masked = dp.mask_code(mask_fences(text))
    links: list[tuple[int, str]] = []
    for number, line in enumerate(masked.split('\n'), 1):
        for match in dp.LINK_RE.finditer(line):
            links.append((number, match.group(1)))
        reference = dp.REF_LINK_RE.match(line)
        if reference:
            links.append((number, reference.group(1)))
    return links


def check_links(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    exceptions_data, errors = load_json(root / LINK_EXCEPTIONS)
    exceptions: list[dict[str, str]] = []
    if errors:
        findings.extend(Finding('links', LINK_EXCEPTIONS, message) for message in errors)
    elif isinstance(exceptions_data, list):
        for entry in exceptions_data:
            if not isinstance(entry, dict) or not all(key in entry for key in ('source', 'target', 'reason')):
                findings.append(Finding('links', LINK_EXCEPTIONS, '例外条目必须包含 source/target/reason'))
                continue
            exceptions.append(entry)
    else:
        findings.append(Finding('links', LINK_EXCEPTIONS, '例外清单必须是数组'))

    used: set[int] = set()
    root_resolved = root.resolve()
    anchors_cache: dict[str, set[str]] = {}

    def anchors_for(path: Path) -> set[str]:
        key = rel_posix(path, root)
        if key not in anchors_cache:
            anchors_cache[key] = collect_anchors(read_text(path))
        return anchors_cache[key]

    for source in all_markdown_sources(root):
        source_rel = rel_posix(source, root)
        text = read_text(source)

        for line_number, raw_target in line_links(text):
            target = raw_target.strip()
            if target.startswith('<') and target.endswith('>'):
                target = target[1:-1]
            if not target or target.startswith('#'):
                if target.startswith('#') and len(target) > 1 and target[1:] not in anchors_for(source):
                    findings.append(Finding('links', source_rel, f'锚点不存在：{target}', line_number))
                continue
            if SKIP_SCHEME_RE.match(target) or target.startswith('/'):
                if target.startswith('/'):
                    findings.append(Finding('links', source_rel, f'链接应使用相对路径：{target}', line_number))
                continue
            if '.artifacts/' in target or target.startswith('.artifacts'):
                continue
            path_part = target.split('#')[0].split('?')[0]
            if not path_part:
                continue
            if '\\' in path_part:
                findings.append(Finding('links', source_rel, f'链接应使用 /：{path_part}', line_number))
                continue
            decoded = unquote(path_part)
            resolved = (source.parent / decoded).resolve()
            try:
                resolved.relative_to(root_resolved)
            except ValueError:
                continue
            if not resolved.exists():
                exception_index = next(
                    (index for index, entry in enumerate(exceptions)
                     if entry['source'] == source_rel and entry['target'] == raw_target and index not in used),
                    None,
                )
                if exception_index is None:
                    findings.append(Finding('links', source_rel, f'目标不存在：{raw_target}', line_number))
                else:
                    used.add(exception_index)
                continue
            fragment = target.partition('#')[2]
            if fragment and resolved.suffix.lower() == '.md' and fragment not in anchors_for(resolved):
                findings.append(Finding('links', source_rel, f'锚点不存在：{target}', line_number))
    for index, entry in enumerate(exceptions):
        if index not in used:
            findings.append(Finding('links', LINK_EXCEPTIONS, f'过期例外（未命中）：{entry["source"]} -> {entry["target"]}'))
    return findings


def check_notes(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    notes = root / NOTES_DIR
    if not notes.is_dir():
        return [Finding('notes', NOTES_DIR, '目录不存在')]
    if not (notes / 'README.md').is_file():
        findings.append(Finding('notes', NOTES_DIR, '缺少 README.md'))
    for current, directories, files in os.walk(notes):
        directories[:] = sorted(directories)
        for name in sorted(files):
            path = Path(current, name)
            rel = rel_posix(path, root)
            if name == 'INDEX.md':
                findings.append(Finding('notes', rel, '禁止 INDEX.md，README.md 才是索引'))
                continue
            if not name.endswith('.md'):
                findings.append(Finding('notes', rel, '笔记目录只允许 Markdown'))
                continue
            if path.parent == notes:
                if name != 'README.md':
                    findings.append(Finding('notes', rel, 'notes 根目录只允许 README.md'))
                continue
            segments = rel.split('/')
            if len(segments) != 5:
                findings.append(Finding('notes', rel, '笔记必须位于 .agents/notes/<lifecycle>/<class>/ 下'))
                continue
            lifecycle, note_class = segments[2], segments[3]
            if lifecycle not in NOTE_LIFECYCLES:
                findings.append(Finding('notes', rel, f'未知生命周期：{lifecycle}'))
                continue
            if note_class not in NOTE_CLASSES:
                findings.append(Finding('notes', rel, f'未知类别：{note_class}'))
                continue
            if not NOTE_FILENAME_RE.match(name):
                findings.append(Finding('notes', rel, '文件名必须是 YYYY-MM-DD-kebab-slug.md'))
                continue
            findings.extend(check_note_body(root, rel, path, lifecycle))
    return findings


def check_note_body(root: Path, rel: str, path: Path, lifecycle: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = read_text(path).split('\n')
    if not lines or not lines[0].startswith('# Agent Note: ') or len(lines[0]) <= len('# Agent Note: '):
        findings.append(Finding('notes', rel, '首行必须是 “# Agent Note: <title>”'))
    if len(lines) < 3 or lines[1].strip():
        findings.append(Finding('notes', rel, '标题后必须空一行', 2))
    expected_status = 'Implemented' if lifecycle == 'implemented' else 'Archived'
    status = next((line.strip() for line in lines[1:6] if line.strip().startswith('Status: ')), None)
    if status != f'Status: {expected_status}':
        findings.append(Finding('notes', rel, f'状态必须是 “Status: {expected_status}”'))
    if lifecycle == 'archived':
        archived = next((line.strip() for line in lines[1:8] if line.strip().startswith('Archived: ')), None)
        if archived is None or not re.fullmatch(r'Archived: \d{4}-\d{2}-\d{2}', archived):
            findings.append(Finding('notes', rel, '归档笔记必须写明 “Archived: YYYY-MM-DD”'))
    sections = [line[3:].strip() for line in lines if line.startswith('## ')]
    if tuple(sections) != NOTE_SECTIONS:
        findings.append(Finding('notes', rel, f'章节必须依次为 {", ".join(NOTE_SECTIONS)}，当前为 {", ".join(sections) or "无"}'))
    return findings


def check_skills(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    skills = root / SKILLS_DIR
    if not skills.is_dir():
        return [Finding('skills', SKILLS_DIR, '目录不存在')]
    for entry in sorted(skills.iterdir()):
        if not entry.is_dir():
            continue
        rel = f'{SKILLS_DIR}/{entry.name}/SKILL.md'
        path = entry / 'SKILL.md'
        if not path.is_file():
            findings.append(Finding('skills', rel, '缺少 SKILL.md'))
            continue
        text = read_text(path)
        if not text.startswith('---\n'):
            findings.append(Finding('skills', rel, '必须以 YAML frontmatter 开始'))
            continue
        closing = text.find('\n---', 4)
        if closing == -1:
            findings.append(Finding('skills', rel, 'frontmatter 未闭合'))
            continue
        frontmatter = text[4:closing]
        body = text[closing + 4:].strip()
        metadata: dict[str, str] = {}
        for line in frontmatter.split('\n'):
            match = re.fullmatch(r'([A-Za-z][A-Za-z0-9_-]*):\s*(.*)', line.strip())
            if match:
                metadata[match.group(1)] = match.group(2).strip().strip('"')
        name = metadata.get('name', '')
        description = metadata.get('description', '')
        if name != entry.name:
            findings.append(Finding('skills', rel, f'name 必须等于目录名：{entry.name}'))
        if not SKILL_NAME_RE.match(name):
            findings.append(Finding('skills', rel, 'name 必须是 kebab-case'))
        if not description:
            findings.append(Finding('skills', rel, '缺少 description'))
        elif len(description) > SKILL_DESCRIPTION_MAX:
            findings.append(Finding('skills', rel, f'description 超过 {SKILL_DESCRIPTION_MAX} 字符'))
        if not body:
            findings.append(Finding('skills', rel, '正文不能为空'))
        elif measure(body) > SKILL_MAX_SIZE:
            findings.append(Finding('skills', rel, f'正文超过 {SKILL_MAX_SIZE} 非空白字符'))
    return findings


def load_pairs(root: Path) -> tuple[list[str], list[str], list[Finding]]:
    findings: list[Finding] = []
    data, errors = load_json(root / PAIRS_MANIFEST)
    findings.extend(Finding('pairing', PAIRS_MANIFEST, message) for message in errors)
    if not isinstance(data, dict):
        return [], [], findings
    pairs = data.get('pairs', [])
    if not isinstance(pairs, list) or not pairs:
        findings.append(Finding('pairing', PAIRS_MANIFEST, 'pairs 必须是非空数组'))
        return [], [], findings
    return pairs, data.get('exclude', []), findings


def load_corpus(root: Path, pairs: list[str]) -> set[str]:
    corpus = set(pairs)
    return corpus


def locale_findings(root: Path, source_rel: str, locale: str, corpus: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    path = root / source_rel
    if not path.is_file():
        return findings
    text = read_text(path)
    lines = text.split('\n')
    if locale == 'en':
        zh_name = Path(source_rel).name[: -len('.en.md')] + '.md'
        switcher = dp.switcher_line('en', zh_name)
    else:
        switcher = dp.switcher_line('zh', Path(source_rel).name)
    for line_number, raw_target in line_links(text):
        if lines[line_number - 1].strip() == switcher:
            continue
        target = raw_target.strip()
        if target.startswith('<') and target.endswith('>'):
            target = target[1:-1]
        if not target or SKIP_SCHEME_RE.match(target) or target.startswith(('/', '#')):
            continue
        path_part = target.split('#')[0].split('?')[0]
        if not path_part.endswith(('.md', '.en.md')):
            continue
        resolved = (root / source_rel).parent / unquote(path_part)
        try:
            rel = resolved.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        plain = rel[:-len('.en.md')] + '.md' if rel.endswith('.en.md') else rel
        if plain not in corpus:
            continue
        if locale == 'zh' and rel.endswith('.en.md'):
            findings.append(Finding('pairing', source_rel, f'中文文档须链接中文配对，而非 {raw_target}', line_number))
        if locale == 'en' and not rel.endswith('.en.md'):
            findings.append(Finding('pairing', source_rel, f'英文文档须链接英文配对（.en.md），而非 {raw_target}', line_number))
    return findings


def compare_pair(root: Path, source_rel: str, findings: list[Finding]) -> None:
    zh_path = root / source_rel
    en_rel = en_path(source_rel)
    en_file = root / en_rel
    record_path = root / (str(Path(source_rel).with_suffix('')) + '.i18n.yaml')
    if not zh_path.is_file():
        findings.append(Finding('pairing', source_rel, '中文主文档不存在'))
        return
    if not en_file.is_file():
        findings.append(Finding('pairing', en_rel, '缺少英文配对'))
        return
    if not record_path.is_file():
        findings.append(Finding('pairing', rel_posix(record_path, root), '缺少 i18n 记录'))
        return
    zh_doc = dp.parse_document(zh_path)
    en_doc = dp.parse_document(en_file)
    findings.extend(Finding('pairing', source_rel, message) for message in zh_doc.parse_errors)
    findings.extend(Finding('pairing', en_rel, message) for message in en_doc.parse_errors)
    if len(zh_doc.sections) != len(en_doc.sections):
        findings.append(Finding('pairing', source_rel, f'小节数量不一致（中文 {len(zh_doc.sections)}，英文 {len(en_doc.sections)}）'))
        return
    for zh_section, en_section in zip(zh_doc.sections, en_doc.sections):
        if zh_section.level != en_section.level:
            findings.append(Finding('pairing', source_rel, f'标题层级不一致：{zh_section.key}', zh_section.line))
            return
    zh_tokens = dp.structure_tokens(zh_doc)
    en_tokens = dp.structure_tokens(en_doc)
    for index, (zh_token, en_token) in enumerate(zip(zh_tokens, en_tokens)):
        if zh_token != en_token:
            section_key = next(
                (token[1] for token in reversed(zh_tokens[: index + 1]) if token[0] == 'section'),
                '',
            )
            findings.append(
                Finding('pairing', source_rel, f'结构不一致：第 {index + 1} 项 {zh_token!r} != {en_token!r}（小节 {section_key}）')
            )
            break
    else:
        if len(zh_tokens) != len(en_tokens):
            findings.append(Finding('pairing', source_rel, '结构项数量不一致'))
    switcher_zh = dp.first_content_after_h1(zh_doc)
    expected_zh = dp.switcher_line('zh', Path(source_rel).name)
    if switcher_zh != expected_zh:
        findings.append(Finding('pairing', source_rel, f'一级标题后缺少语言切换行：{expected_zh}'))
    switcher_en = dp.first_content_after_h1(en_doc)
    expected_en = dp.switcher_line('en', Path(source_rel).name)
    if switcher_en != expected_en:
        findings.append(Finding('pairing', en_rel, f'一级标题后缺少语言切换行：{expected_en}'))
    record, record_errors = dp.parse_record(read_text(record_path))
    for message in record_errors:
        findings.append(Finding('pairing', rel_posix(record_path, root), message))
    computed, alignment_error = dp.aligned_hashes(zh_doc, en_doc)
    if alignment_error is not None:
        findings.append(Finding('pairing', source_rel, alignment_error))
        return
    for key, (en_hash, zh_hash) in computed.items():
        if key not in record:
            findings.append(Finding('pairing', rel_posix(record_path, root), f'记录缺少小节：{key}'))
            continue
        en_record, zh_record = record[key]
        if zh_record != zh_hash:
            findings.append(Finding('pairing', rel_posix(record_path, root), f'中文哈希过期：{key}'))
        if en_record != en_hash:
            findings.append(Finding('pairing', rel_posix(record_path, root), f'英文哈希过期：{key}'))
    for key in record:
        if key not in computed:
            findings.append(Finding('pairing', rel_posix(record_path, root), f'记录含多余小节：{key}'))


def write_pairs(root: Path, pairs: list[str], sources: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    targets = pairs if not sources else sources
    for source_rel in targets:
        source_rel = Path(source_rel).as_posix()
        zh_path = root / source_rel
        en_file = root / en_path(source_rel)
        record_path = root / (str(Path(source_rel).with_suffix('')) + '.i18n.yaml')
        if not zh_path.is_file():
            findings.append(Finding('pairing', source_rel, '中文主文档不存在'))
            continue
        if not en_file.is_file():
            findings.append(Finding('pairing', en_path(source_rel), '缺少英文配对'))
            continue
        zh_doc = dp.parse_document(zh_path)
        en_doc = dp.parse_document(en_file)
        computed, alignment_error = dp.aligned_hashes(zh_doc, en_doc)
        if alignment_error is not None:
            findings.append(Finding('pairing', source_rel, f'{alignment_error}，拒绝重记'))
            continue
        record_path.write_text(dp.render_record(computed), encoding='utf-8', newline='\n')
        print(f'记录已更新：{rel_posix(record_path, root)}')
    return findings


def list_pairs(root: Path, pairs: list[str]) -> None:
    for source_rel in pairs:
        zh_path = root / source_rel
        en_file = root / en_path(source_rel)
        record_path = root / (str(Path(source_rel).with_suffix('')) + '.i18n.yaml')
        if not zh_path.is_file() or not en_file.is_file() or not record_path.is_file():
            print(f'missing     {source_rel}')
            continue
        try:
            zh_doc = dp.parse_document(zh_path)
            en_doc = dp.parse_document(en_file)
            record, record_errors = dp.parse_record(read_text(record_path))
            computed, alignment_error = dp.aligned_hashes(zh_doc, en_doc)
        except OSError as error:
            print(f'error       {source_rel}: {error}')
            continue
        ok = not record_errors and alignment_error is None and record == computed
        print(f'{"ok" if ok else "out-of-sync"}  {source_rel}')


def check_pairing(root: Path) -> list[Finding]:
    pairs, _exclude, findings = load_pairs(root)
    if findings:
        return findings
    corpus = load_corpus(root, pairs)
    registered = {en_path(item) for item in pairs}
    for source_rel in pairs:
        compare_pair(root, source_rel, findings)
        findings.extend(locale_findings(root, source_rel, 'zh', corpus))
        findings.extend(locale_findings(root, en_path(source_rel), 'en', corpus))
    for base in ('docs', '.agents'):
        for source in walk_markdown(root, base):
            rel = rel_posix(source, root)
            if rel.endswith('.en.md') and rel not in registered:
                findings.append(Finding('pairing', rel, '英文配对未登记在 scripts/doc-pairs.json'))
    return findings


CHECKS = {
    'budgets': check_budgets,
    'pairing': lambda root: check_pairing(root),
    'wrap': check_wrap,
    'links': check_links,
    'notes': check_notes,
    'skills': check_skills,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='AstroPhotoFlow 文档门禁')
    parser.add_argument('rules', nargs='*', default=['all'], help='budgets/pairing/wrap/links/notes/skills/all')
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--report', action='store_true', help='只报告，不因违规失败')
    parser.add_argument('--write', nargs='+', metavar='SOURCE', help='重记指定中文主文档的 i18n 记录')
    parser.add_argument('--write-all', action='store_true', help='重记清单内全部配对记录')
    parser.add_argument('--list', action='store_true', help='列出配对状态，不因缺失失败')
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    rules = args.rules or ['all']
    if 'all' in rules:
        rules = list(CHECKS)
    unknown = [rule for rule in rules if rule not in CHECKS]
    if unknown:
        print(f'未知规则：{", ".join(unknown)}', file=sys.stderr)
        return 2
    if args.write or args.write_all:
        if rules != ['pairing']:
            print('--write 只能与 pairing 一起使用', file=sys.stderr)
            return 2
        pairs, _errors, manifest_findings = load_pairs(root)
        findings = manifest_findings + write_pairs(root, pairs, [] if args.write_all else args.write)
        for finding in findings:
            print(finding)
        return 0 if not findings else 1
    if args.list:
        pairs, _errors, manifest_findings = load_pairs(root)
        if manifest_findings:
            for finding in manifest_findings:
                print(finding)
            return 1
        list_pairs(root, pairs)
        return 0
    findings: list[Finding] = []
    for rule in rules:
        findings.extend(CHECKS[rule](root))
    if findings:
        for finding in findings:
            print(finding)
        print(f'{len(findings)} 项违规。规则见 docs/AGENTS.md。')
        return 0 if args.report else 1
    print('文档门禁通过。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
