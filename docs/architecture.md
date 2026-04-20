# Architecture

## Shared Core First

The runtime lives in `shared_core/Code`. Variant folders should stay thin and carry only the pieces that truly differ:

- `app_config.py`
- launch/build wrappers
- local `Data/`
- variant-specific tests
- variant-specific docs

Everything else should default to shared-core ownership:

- database schema and helpers
- import pipelines
- GUI behavior
- exports/reporting
- sync and update checks

## Active Runtime Split

- `Code/db/`
  - SQLite schema
  - search/index maintenance
  - local snapshot helpers
  - sync-state persistence primitives for local cache revision tracking
  - record lookup/update primitives
- `Code/gui/`
  - main window and dialogs
  - search/filter behavior
  - table presentation and interaction
  - disconnected view-only mode (edit/import actions disabled)
- `Code/importer/`
  - workbook parsing
  - merge/full import orchestration
- `Code/sync/`
  - shared-first cache refresh service
  - shared-to-local snapshot coordination
  - Qt worker bridge for off-thread sync/import/mutation work
  - update-manifest checks

## Shared-First Cache Sync Flow

1. Open the local SQLite cache for the current source copy.
2. Resolve the variant shared DB path and treat it as the authoritative source of truth.
3. Refresh local cache from shared in background sync cycles.
4. Execute edits/imports only when shared is reachable; refresh local cache after shared writes.
5. When shared is unavailable, keep view/search active while disabling edit/import actions.
6. Communicate disconnected/busy state via status bar messaging; do not surface modal loss popups for background sync.
7. Keep update checks tied to the shared release manifest.
