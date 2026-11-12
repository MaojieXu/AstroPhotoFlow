"""Shared fixtures for documentation gate tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

ZH = '''# 示例项目

[English](README.en.md) | 中文

## 概览

这是一段单行正文，链接到 [文档入口](docs/README.md)。
'''
EN = '''# Example project

English | [中文](README.md)

## Overview

This is one single-line paragraph linking to [docs](docs/README.md).
'''
NOTE = '''# Agent Note: 示例笔记

Status: Implemented

## Problem

问题描述。

## Decision

决定描述。

## Alternatives considered

无。

## Consequences

后果描述。
'''
SKILL = '''---
name: demo-skill
description: 演示技能，用于门禁测试。
---

# Demo

按步骤执行。
'''


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def write_json(path: Path, data: object) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False))


@pytest.fixture()
def write():
    return write_text


@pytest.fixture()
def write_json_file():
    return write_json


@pytest.fixture()
def readme_text() -> str:
    return ZH


@pytest.fixture()
def note_text() -> str:
    return NOTE


@pytest.fixture()
def skill_text() -> str:
    return SKILL


@pytest.fixture()
def record_pair():
    def record(root: Path) -> None:
        import verify_docs

        assert verify_docs.main(['pairing', '--write', 'README.md', '--root', str(root)]) == 0

    return record


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / 'repo'
    write_text(root / 'README.md', ZH)
    write_text(root / 'README.en.md', EN)
    write_text(root / 'docs' / 'README.md', '# 文档入口\n\n没有英文配对。\n')
    write_text(root / '.agents' / 'notes' / 'README.md', '# Agent Notes\n\n索引。\n')
    write_text(root / '.agents' / 'notes' / 'implemented' / 'process' / '2026-11-06-demo.md', NOTE)
    write_text(root / '.agents' / 'skills' / 'demo-skill' / 'SKILL.md', SKILL)
    write_json(root / 'scripts' / 'doc-pairs.json', {'pairs': ['README.md'], 'exclude': []})
    write_json(
        root / 'scripts' / 'doc-budgets.json',
        {
            'files': {'README.md': {'zh': 3000, 'en': 7000}},
            'agents_md': {'default': 4000, 'overrides': {}, 'exclude': ['frontend/AGENTS.md', 'engine/**']},
        },
    )
    write_json(root / 'scripts' / 'doc-link-exceptions.json', [])
    return root


@pytest.fixture()
def paired_repo(repo: Path, record_pair) -> Path:
    record_pair(repo)
    return repo
