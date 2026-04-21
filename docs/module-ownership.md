# Module Ownership

## Shared Core (`shared_core/Code`)

`db/`
- Owns schema, CRUD/search repositories, snapshot replacement/copy/import, sync-state persistence.
- `database.py` is the compatibility facade for callers.
- `legacy_sync_queue.py` APIs are compatibility-only and not runtime-critical for shared-first sync.

`sync/`
- Owns shared availability checks, revision checks, cache refresh behavior, and shared mutation orchestration.
- `service.py` is the public sync facade.
- `worker.py` owns the Qt background execution bridge.

`gui/`
- Owns window shell, table behavior, dialogs, search/filter, and action routing.
- `main_window.py` remains the integration point.
- helper modules (`main_window_ui.py`, `main_window_sync.py`, `main_window_actions.py`, `main_window_search.py`) own extracted responsibilities.

`importer/`
- Owns workbook parsing, matching, dedupe/merge logic, and import persistence orchestration.
- `pipeline.py` remains the public facade.

`reporting/`, `utils/`
- Own shared export/report generation and runtime utility helpers.

## Template Wrapper (`Lab_Template`)

Owns only variant-specific concerns:

- `app_config.py` metadata, import profile, feature flags, shared path settings
- launcher/build wiring (`main.py`, `build.py`)
- variant-local tests and local `Data/` assets

## Boundary Rule

If a change affects runtime behavior that should apply to more than one variant, it belongs in `shared_core/Code`, not inside the template wrapper.