# Migration Notes

## What Changed in the Template Refactor

- Monolithic runtime modules were decomposed into focused submodules while preserving public APIs.
- `Code.db.database`, `Code.sync.service`, and `Code.importer.pipeline` are now facades.
- Shared-first sync behavior remains authoritative-shared + local-cache.
- Main-window responsibilities were split into helper modules for UI/sync/actions/search logic.
- New characterization tests were added for DB, snapshot, sync, and main-window action routing.
- Development test tooling moved to root `requirements-dev.txt`.

## Compatibility Preserved

- `Lab_Template/main.py` still exposes `main()`.
- Existing `AppConfig` keys are unchanged.
- Existing import paths for DB/sync/pipeline public functions remain valid.
- Legacy outbox/tombstone functions remain callable through DB facade exports.

## Operational Behavior Kept

- Shared sync disabled: local-only behavior remains available.
- Shared unavailable: app remains usable for view/search with mutation gating.
- Background sync busy/unavailable states remain non-blocking and status-bar driven.

## Test Notes

- Run template tests from `Lab_Template/`:
  - `pip install -r ..\\requirements-dev.txt`
  - `python -m pytest tests -q`
- Import parser tests still require optional workbook stack (`openpyxl`, `xlrd`) from runtime requirements.