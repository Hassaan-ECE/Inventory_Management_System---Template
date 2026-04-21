# Maintenance Guide

## Add a New Equipment Field Safely

1. Update `Code/db/models.py` `Equipment` dataclass.
2. Update schema defaults/migrations in DB implementation (`Code/db/_database_impl.py`).
3. Update DB CRUD/search mappings in repository layer.
4. Update GUI dialogs/table formatting/search filters where relevant.
5. Update import pipeline merge helpers if field participates in merge logic.
6. Add tests for CRUD/search/import/sync behavior for the new field.

## Add a New Search/Filter Field

1. Add field to `app_config.py` `table_fields`/`filter_fields`.
2. Update search query behavior in `gui/main_window_search.py` and DB search mapping.
3. Validate column visibility/header menu and quick-edit behavior.

## Modify Import Rules

1. Update parser modules for source extraction.
2. Update merge helper behavior in `pipeline_merge_helpers.py`.
3. Keep `pipeline.py` facade signatures unchanged.
4. Add characterization/integration tests for the new rule.

## Modify Shared Sync Behavior

1. Keep public `Code.sync.service` signatures stable.
2. Put path/revision logic in `sync/paths.py` or `sync/revision.py`.
3. Put mutation/import refresh logic in `sync/mutations.py`.
4. Verify unavailable/busy modes remain non-blocking in UI.

## Compatibility Checklist for Refactors

- `Code.db.database` import surface unchanged.
- `Code.sync.service` import surface unchanged.
- `Code.importer.pipeline` entry points unchanged.
- `Lab_Template/main.py` still exposes `main()`.
- Existing `AppConfig` keys untouched.

## Release Readiness

- Run `python -m pytest tests -q` from `Lab_Template/`.
- Launch app manually and validate:
  - startup with empty DB
  - import flow
  - search/filter/table actions
  - archive/verify/delete flows
  - export commands
  - shared-sync status behavior (if enabled)