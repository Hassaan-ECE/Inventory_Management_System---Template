# Code Map

## Top-Level Runtime Flow

1. `Lab_Template/main.py` calls `run_app(...)` from `Code.app_bootstrap`.
2. App opens local DB connection and constructs `MainWindow`.
3. Search/view operations read local cache via DB repo functions.
4. Import/mutation operations route through local mode or shared-sync mode.
5. Shared mode refreshes local cache from authoritative shared DB snapshots.

## Module Map

`Code/db`
- `database.py`: compatibility facade for external imports.
- `schema.py`: connection + table/bootstrap primitives.
- `equipment_repo.py`: equipment CRUD/search/stats.
- `import_repo.py`: raw-cell/import-issue reads/writes.
- `snapshot_repo.py`: snapshot fetch/replace/copy/import.
- `sync_state_repo.py`: revision/hash/client identity state.
- `legacy_sync_queue.py`: compatibility outbox/applied/tombstone APIs.

`Code/sync`
- `service.py`: public sync facade (stable import surface).
- `paths.py`: path/shared-root resolution helpers.
- `revision.py`: status and revision checks.
- `mutations.py`: shared write/import orchestration helpers.
- `worker.py`: Qt worker for off-thread sync tasks.

`Code/gui`
- `main_window.py`: integration shell.
- `main_window_ui.py`: window sizing/UI helpers.
- `main_window_sync.py`: worker lifecycle/request helpers.
- `main_window_actions.py`: CRUD/archive/import action handlers.
- `main_window_search.py`: search/filter/result-label logic.
- dialogs/table/theme/ui components.

`Code/importer`
- `pipeline.py`: public facade with profile-strategy dispatch.
- `pipeline_full.py`: full-import strategy runner.
- `pipeline_merge.py`: merge-import strategy runner.
- `pipeline_merge_helpers.py`: merge/dedupe/match helpers.
- parser modules: workbook-specific extraction.

## Data Flow Notes

- Local DB schema is always created/guarded before operations.
- Shared sync uses snapshot replacement to keep local cache aligned.
- GUI actions call shared mutation APIs when shared sync is enabled and available.
- Import pipelines write equipment/import_issues/raw_cells in one transactional flow.