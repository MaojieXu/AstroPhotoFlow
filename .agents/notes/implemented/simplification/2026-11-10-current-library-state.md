# Agent Note: Current library state

Status: Implemented

## Problem

Single-file versions, dataset versions, standalone calibration configurations and Master declaration revisions introduced multiple identities and historical selections throughout a local image-processing workflow. The initial product requires straightforward import, organization, processing and explicit result saving.

## Decision

Assets now own their registered original and use one asset ID. Datasets own their current ordered subframes and shared calibration. Standalone calibration and Master declarations retain current settings. Project and canvas references use asset or dataset IDs, and each software call resolves current inputs into its existing execution record. Import observations, equipment snapshots, content hashes, revision checks, idempotent receipts and deletion protection remain part of the implementation.

The existing dev workspace was stopped and rebuilt in place with the current database baseline and frontend. Its old test database, managed originals, previews, staging, workflows and configuration were cleared within the verified workspace boundary.

## Alternatives considered

Keeping immutable dataset revisions would preserve old saved selections but retain a second identity and history-management surface. Renaming original versions would retain the dual model. The user selected current-state editing throughout the library and initialization of development data from a fresh schema.

## Consequences

Editing dataset membership, order or calibration changes the inputs selected by the next software call. Partial selections use asset IDs and fail when selected assets leave the dataset. Registered original bytes remain protected by hash checks, and changed content is restored or imported as another asset. The database baseline and public contracts require the current schema. Previous database and workflow formats have no compatibility path.

The user requested implementation and artifact generation with automated tests and end-to-end acceptance skipped. Static checks, schema generation and production frontend building were performed. Runtime behavior awaits user acceptance.
