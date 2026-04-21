# Architecture

## Runtime Model

The runtime is shared-first:

1. The shared database is authoritative when shared sync is enabled.
2. The local database is a cache optimized for startup/view/search.
3. UI remains usable for view/search when shared storage is unavailable.
4. Mutations/imports are gated by shared availability in shared-sync mode.

## Code Ownership Boundary

- `shared_core/Code/` owns runtime behavior and contracts.
- `Lab_Template/` owns variant configuration, launcher/build wiring, and variant tests.

## Runtime Module Layout

- `Code/db/`
  - `database.py` compatibility facade
  - `schema.py` connection/table bootstrap
  - `equipment_repo.py` equipment CRUD/search/stats
  - `import_repo.py` raw-cell/import-issue persistence
  - `snapshot_repo.py` snapshot fetch/replace/copy/import
  - `sync_state_repo.py` revision/hash/client state
  - `legacy_sync_queue.py` compatibility-only outbox/tombstone helpers
- `Code/sync/`
  - `service.py` public facade for sync operations
  - `paths.py` path/shared-root resolution helpers
  - `revision.py` status/revision checks
  - `mutations.py` shared mutation/import helpers
  - `worker.py` Qt thread bridge for background sync
- `Code/gui/`
  - `main_window.py` integration shell
  - `main_window_ui.py` window sizing/ui helpers
  - `main_window_sync.py` worker lifecycle helpers
  - `main_window_actions.py` CRUD/import action handlers
  - `main_window_search.py` search/filter result logic
  - dialogs/table/theme/search helper modules
- `Code/importer/`
  - `pipeline.py` public import facade
  - `pipeline_full.py` full-import strategy dispatch
  - `pipeline_merge.py` merge-import strategy dispatch
  - `pipeline_merge_helpers.py` merge/match/dedupe helpers
  - parser modules (`master_parser`, `survey_parser`, `me_parser`) and normalizer/matching

## Public Interfaces Kept Stable

- `Code.db.database` import surface remains stable via facade re-exports.
- `Code.sync.service` function signatures remain stable.
- `Code.importer.pipeline` entry points remain stable.
- `Lab_Template/main.py` keeps `main()` as the entrypoint.