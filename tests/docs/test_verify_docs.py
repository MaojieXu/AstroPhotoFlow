"""Unit tests for scripts/verify_docs.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import verify_docs as v


def messages(findings: list[v.Finding]) -> str:
    return '\n'.join(str(finding) for finding in findings)


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding='utf-8'))


def save(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8', newline='\n')


def budget_manifest(root: Path) -> Path:
    return root / 'scripts' / 'doc-budgets.json'


# ---------------------------------------------------------------- budgets


def test_budgets_accept_fixture(repo: Path) -> None:
    assert v.check_budgets(repo) == []


def test_budgets_report_over_limit(repo: Path) -> None:
    data = load(budget_manifest(repo))
    data['files']['README.md'] = {'zh': 10, 'en': 7000}
    save(budget_manifest(repo), data)
    output = messages(v.check_budgets(repo))
    assert 'README.md' in output and '超出预算' in output


def test_budgets_report_missing_registered_file(repo: Path) -> None:
    data = load(budget_manifest(repo))
    data['files']['docs/missing.md'] = 100
    save(budget_manifest(repo), data)
    output = messages(v.check_budgets(repo))
    assert 'docs/missing.md' in output and '不存在' in output


def test_budgets_report_invalid_limit(repo: Path) -> None:
    data = load(budget_manifest(repo))
    data['files']['README.md'] = {'zh': 0, 'en': 7000}
    save(budget_manifest(repo), data)
    assert '上限必须是正整数' in messages(v.check_budgets(repo))


def test_budgets_apply_agents_default_and_overrides(repo: Path, write) -> None:
    write(repo / 'AGENTS.md', '# Agents\n\n' + '字' * 100 + '\n')
    assert v.check_budgets(repo) == []
    write(repo / 'AGENTS.md', '# Agents\n\n' + '字' * 5000 + '\n')
    assert '超出预算' in messages(v.check_budgets(repo))
    data = load(budget_manifest(repo))
    data['agents_md']['overrides'] = {'AGENTS.md': 6000}
    save(budget_manifest(repo), data)
    assert v.check_budgets(repo) == []


def test_budgets_skip_excluded_agents_files(repo: Path, write) -> None:
    write(repo / 'frontend' / 'AGENTS.md', '# Vendored\n\n' + '字' * 9000 + '\n')
    assert v.check_budgets(repo) == []


# ------------------------------------------------------------------- wrap


def test_wrap_accepts_single_line_paragraphs(repo: Path) -> None:
    assert v.check_wrap(repo) == []


def test_wrap_reports_hard_wrapped_paragraph(repo: Path, write) -> None:
    write(repo / 'docs' / 'wrapped.md', '# 标题\n\n第一行\n第二行\n')
    output = messages(v.check_wrap(repo))
    assert 'docs/wrapped.md' in output and '段落跨多个物理行' in output


def test_wrap_ignores_code_tables_and_frontmatter(repo: Path, write) -> None:
    text = (
        '---\ntitle: x\n---\n\n# 标题\n\n单行段落。\n\n'
        '| 列一 | 列二 |\n| --- | --- |\n| 甲 | 乙 |\n\n'
        '```text\n第一行\n第二行\n```\n'
    )
    write(repo / 'docs' / 'ok.md', text)
    assert v.check_wrap(repo) == []


def test_wrap_reports_list_item_continuation(repo: Path, write) -> None:
    write(repo / 'docs' / 'list.md', '# 标题\n\n- 第一行\n  第二行\n')
    assert '段落跨多个物理行' in messages(v.check_wrap(repo))


# ------------------------------------------------------------------ links


def test_links_accept_fixture(repo: Path) -> None:
    assert v.check_links(repo) == []


def test_links_report_missing_target(repo: Path, write) -> None:
    write(repo / 'docs' / 'README.md', '# 文档入口\n\n[缺失](missing.md)\n')
    assert '目标不存在' in messages(v.check_links(repo))


def test_links_report_missing_anchor(repo: Path, write) -> None:
    write(repo / 'docs' / 'README.md', '# 文档入口\n\n[锚点](README.md#nope)\n')
    assert '锚点不存在' in messages(v.check_links(repo))


def test_links_accept_existing_and_self_anchors(repo: Path, write) -> None:
    text = '# 文档入口\n\n<a id="manual"></a>\n\n## 第二节\n\n[本节](#manual) [标题](#第二节)\n'
    write(repo / 'docs' / 'README.md', text)
    assert v.check_links(repo) == []


def test_links_skip_external_code_and_artifacts(repo: Path, write) -> None:
    text = (
        '# 文档入口\n\n[外链](https://example.com/x) `[代码](missing.md)` '
        '[产物](.artifacts/build/out.txt)\n'
    )
    write(repo / 'docs' / 'README.md', text)
    assert v.check_links(repo) == []


def test_links_rejects_absolute_paths(repo: Path, write) -> None:
    write(repo / 'docs' / 'README.md', '# 文档入口\n\n[绝对](/abs/path.md)\n')
    assert '相对路径' in messages(v.check_links(repo))


def test_links_exceptions_satisfy_and_expire(repo: Path, write) -> None:
    write(repo / 'docs' / 'README.md', '# 文档入口\n\n[曾用路径](old/name.md)\n')
    exceptions = repo / 'scripts' / 'doc-link-exceptions.json'
    save(exceptions, [{'source': 'docs/README.md', 'target': 'old/name.md', 'reason': '历史路径'}])
    assert v.check_links(repo) == []
    save(exceptions, [{'source': 'other.md', 'target': 'nowhere.md', 'reason': '不再命中'}])
    assert '过期例外' in messages(v.check_links(repo))
    save(exceptions, [{'source': 'docs/README.md', 'target': 'old/name.md'}])
    assert '必须包含' in messages(v.check_links(repo))


# ------------------------------------------------------------------ notes


def test_notes_accept_fixture(repo: Path) -> None:
    assert v.check_notes(repo) == []


def test_notes_report_bad_filename(repo: Path, write) -> None:
    write(repo / '.agents' / 'notes' / 'implemented' / 'process' / 'bad-name.md', '# Agent Note: x\n\nStatus: Implemented\n\n## Problem\n\nx\n\n## Decision\n\nx\n\n## Alternatives considered\n\nx\n\n## Consequences\n\nx\n')
    assert 'YYYY-MM-DD-kebab-slug.md' in messages(v.check_notes(repo))


def test_notes_report_unknown_class_and_lifecycle(repo: Path, write) -> None:
    write(repo / '.agents' / 'notes' / 'implemented' / 'other' / '2026-11-06-x.md', '# Agent Note: x\n\nStatus: Implemented\n')
    assert '未知类别' in messages(v.check_notes(repo))
    write(repo / '.agents' / 'notes' / 'proposed' / 'process' / '2026-11-06-x.md', '# Agent Note: x\n\nStatus: Proposed\n')
    assert '未知生命周期' in messages(v.check_notes(repo))


def test_notes_report_header_and_status(repo: Path, write, note_text: str) -> None:
    note = repo / '.agents' / 'notes' / 'implemented' / 'process' / '2026-11-06-demo.md'
    write(note, note_text.replace('# Agent Note: 示例笔记', '# 示例笔记'))
    assert '首行' in messages(v.check_notes(repo))
    write(note, note_text.replace('Status: Implemented', 'Status: Proposed'))
    assert 'Status: Implemented' in messages(v.check_notes(repo))


def test_notes_require_ordered_sections(repo: Path, write, note_text: str) -> None:
    note = repo / '.agents' / 'notes' / 'implemented' / 'process' / '2026-11-06-demo.md'
    write(note, note_text.replace('## Decision', '## Proposal'))
    assert '章节必须依次为' in messages(v.check_notes(repo))


def test_notes_forbid_index_and_extra_root_files(repo: Path, write) -> None:
    write(repo / '.agents' / 'notes' / 'INDEX.md', '# Index\n')
    assert '禁止 INDEX.md' in messages(v.check_notes(repo))
    write(repo / '.agents' / 'notes' / 'extra.md', '# Extra\n')
    assert '根目录只允许 README.md' in messages(v.check_notes(repo))


# ----------------------------------------------------------------- skills


def test_skills_accept_fixture(repo: Path) -> None:
    assert v.check_skills(repo) == []


def test_skills_report_name_mismatch_and_bad_name(repo: Path, write, skill_text: str) -> None:
    skill = repo / '.agents' / 'skills' / 'demo-skill' / 'SKILL.md'
    write(skill, skill_text.replace('name: demo-skill', 'name: other'))
    assert 'name 必须等于目录名' in messages(v.check_skills(repo))
    write(skill, skill_text.replace('name: demo-skill', 'name: Bad_Name'))
    assert 'kebab-case' in messages(v.check_skills(repo))


def test_skills_report_missing_frontmatter(repo: Path, write) -> None:
    write(repo / '.agents' / 'skills' / 'demo-skill' / 'SKILL.md', '# Demo\n\n正文。\n')
    assert 'frontmatter' in messages(v.check_skills(repo))


def test_skills_report_description_and_body_limits(repo: Path, write, skill_text: str) -> None:
    skill = repo / '.agents' / 'skills' / 'demo-skill' / 'SKILL.md'
    write(skill, skill_text.replace('演示技能，用于门禁测试。', 'x' * 501))
    assert '超过 500' in messages(v.check_skills(repo))
    write(skill, skill_text.replace('按步骤执行。', '字' * 8001))
    assert '超过 8000' in messages(v.check_skills(repo))


def test_skills_report_missing_skill_file(repo: Path) -> None:
    (repo / '.agents' / 'skills' / 'empty-skill').mkdir()
    assert '缺少 SKILL.md' in messages(v.check_skills(repo))


# ---------------------------------------------------------------- pairing


def test_pairing_accepts_fresh_record(paired_repo: Path) -> None:
    assert v.check_pairing(paired_repo) == []


def test_pairing_reports_stale_hash(paired_repo: Path, write, readme_text: str) -> None:
    write(paired_repo / 'README.md', readme_text.replace('这是一段单行正文', '这是另一段单行正文'))
    assert '中文哈希过期' in messages(v.check_pairing(paired_repo))


def test_pairing_reports_missing_english(repo: Path) -> None:
    (repo / 'README.en.md').unlink()
    assert '缺少英文配对' in messages(v.check_pairing(repo))


def test_pairing_reports_missing_record(repo: Path) -> None:
    assert '缺少 i18n 记录' in messages(v.check_pairing(repo))


def test_pairing_requires_switcher_line(paired_repo: Path, write, readme_text: str) -> None:
    write(paired_repo / 'README.md', readme_text.replace('[English](README.en.md) | 中文\n\n', ''))
    assert '语言切换行' in messages(v.check_pairing(paired_repo))


def test_pairing_reports_structure_mismatch(paired_repo: Path) -> None:
    english = paired_repo / 'README.en.md'
    english.write_text(english.read_text(encoding='utf-8') + '\n- extra item\n', encoding='utf-8', newline='\n')
    output = messages(v.check_pairing(paired_repo))
    assert '结构不一致' in output or '结构项数量不一致' in output


def test_pairing_reports_wrong_locale_link(paired_repo: Path) -> None:
    english = paired_repo / 'README.en.md'
    english.write_text(
        english.read_text(encoding='utf-8') + '\nSee [中文](README.md).\n',
        encoding='utf-8',
        newline='\n',
    )
    assert '英文文档须链接英文配对' in messages(v.check_pairing(paired_repo))


def test_pairing_reports_unregistered_english_file(repo: Path, write) -> None:
    write(repo / 'docs' / 'extra.en.md', '# Extra\n')
    assert '英文配对未登记' in messages(v.check_pairing(repo))


def test_pairing_reports_extra_record_section(paired_repo: Path, write) -> None:
    record_file = paired_repo / 'README.i18n.yaml'
    text = record_file.read_text(encoding='utf-8') + '/stale:\n  en: 0123456789abcdef\n  zh: 0123456789abcdef\n'
    write(record_file, text)
    assert '记录含多余小节' in messages(v.check_pairing(paired_repo))


# -------------------------------------------------------------------- main


def test_main_all_passes(paired_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert v.main(['all', '--root', str(paired_repo)]) == 0
    assert '文档门禁通过' in capsys.readouterr().out


def test_main_reports_failures_and_report_mode(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert v.main(['all', '--root', str(repo)]) == 1
    assert '项违规' in capsys.readouterr().out
    assert v.main(['all', '--root', str(repo), '--report']) == 0


def test_main_write_requires_pairing_rule(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert v.main(['all', '--write', 'README.md', '--root', str(repo)]) == 2
    assert '--write 只能与 pairing' in capsys.readouterr().err


def test_main_list_reports_ok(paired_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert v.main(['pairing', '--list', '--root', str(paired_repo)]) == 0
    assert 'ok  README.md' in capsys.readouterr().out


def test_main_list_reports_missing(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert v.main(['pairing', '--list', '--root', str(repo)]) == 0
    assert 'missing' in capsys.readouterr().out


def test_main_rejects_unknown_rule(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert v.main(['nope', '--root', str(repo)]) == 2
    assert '未知规则' in capsys.readouterr().err


def test_write_rejects_section_count_mismatch(repo: Path, write) -> None:
    write(repo / 'README.en.md', '# Example project\n')
    findings = v.write_pairs(repo, ['README.md'], ['README.md'])
    assert findings and '小节数量不一致' in findings[0].message


def test_record_helper_roundtrip(repo: Path, record_pair) -> None:
    record_pair(repo)
    assert (repo / 'README.i18n.yaml').is_file()
    assert v.check_pairing(repo) == []
