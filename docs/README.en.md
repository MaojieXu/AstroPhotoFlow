# Documentation Entry

English | [中文](README.md)

Find the document for your task here. Fact ownership, writing requirements, and gates are defined in [Documentation Rules](AGENTS.md).

## Task Entry

| I want to… | Read |
| --- | --- |
| Understand product requirements and boundaries | [Product Requirements](product/README.en.md) |
| Locate modules, data, and dependencies | [Architecture](architecture.en.md) |
| Change one subsystem | [Subsystem Index](subsystems/README.en.md) |
| Set up the environment and run local commands | [Development](development.en.md) |
| Run tests and write verification receipts | [Testing](testing.en.md) |
| Cut a release | [Release](release.en.md) |
| Look up APIs and generated artifacts | [References](references.en.md) |
| Operate the workbench | [User Guide](user/workbench.en.md) |
| Understand decisions already made | [Agent Notes](../.agents/notes/README.md) |
| Maintain Chinese/English pairs | [Bilingual Documentation](i18n/README.en.md) |

## Conventions

- Documentation records the current state only; history, abandoned options, and discussion belong in Agent Notes, commit messages, or pull requests, never in the body.
- Every Chinese primary document has an English pair, and changing one side requires changing the other.
- The gate entry point is `pnpm check:docs`, and CI runs the same command as local development.
