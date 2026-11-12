# Bilingual Documentation

English | [中文](README.md)

This repository keeps documentation primarily in Chinese, with English as a paired translation. This page defines the three-file structure, records, and gates; read it before writing or changing any paired document.

## File Trio

Each paired document has three files in the same directory: `foo.md` is the Chinese primary document, `foo.en.md` is the English translation, and `foo.i18n.yaml` records the content hashes of both sides. Commit all three together; a missing file fails the gate.

## Switcher Line

A Chinese primary document puts `[English](foo.en.md) | 中文` on a line after the H1 heading and a blank line. An English document puts `English | [中文](foo.md)` after the H1 heading and a blank line. The switcher line does not participate in the body hash, but the gate checks its structure and position.

## Record File

`foo.i18n.yaml` opens with four comment lines explaining that the gate generates the file, that hashes are recorded per section for both sides, and how to re-record. After that, each section is a group of three lines: a section key of the form `/<h1-slug>/<h2-slug>`, then `  en: <16 hex digits>` and `  zh: <16 hex digits>`. Blank lines and comment lines are ignored; every other line is parsed in groups of three. A duplicate key or a malformed group is treated as corruption.

## Sections and Hashes

Each heading opens a section, and a subsection key carries the slug path of its ancestor headings; the gate deduplicates repeated headings with a `~2` suffix. Sections align in order on both sides, and both sides must have the same number of sections. A hash is the first 16 hex digits of sha256 over the section's top-level text blocks joined by lines, excluding fenced code blocks. A section empty on both sides produces no record.

## Structural Mirroring

Chinese and English must be structurally identical: the same heading depths and order, the same list kinds, start numbers, and item counts, the same table row and column counts, code blocks with identical info strings and bodies, and links that point at the same semantic target. Fix the structure before re-recording hashes.

## Link Locale

Chinese documents link to Chinese pairs with paths ending in `.md`; English documents link to English pairs with paths ending in `.en.md`. Links to targets outside the paired corpus keep the path the author wrote. The language switcher line is the only exception.

## Scope

The scope is listed in `scripts/doc-pairs.json`, which registers Chinese primary files only. `AGENTS.md`, `.agents/notes/**`, and `.agents/skills/**` are Chinese-only and are not paired; `docs/api/*.json`, `reference/**`, `frontend/**`, and `engine/**` are out of scope.

## Update Workflow

Change the Chinese primary document first, then the English translation. Run `python scripts/verify_docs.py pairing --write <Chinese primary file>` to re-record hashes for that pair, then run `pnpm check:docs`. `pairing --list` only reports ok, missing, and out-of-sync and never modifies files; `--write-all` re-records everything and is only for bulk migrations.

## Responsibility Boundary

A passing hash check confirms that both sides match their recorded contents. Assessing translation quality and semantic equivalence requires human judgment.
