# Sync Runtime Reference

## Shared-First Contract

- Shared DB is authoritative when shared sync is enabled.
- Local DB is a cache optimized for startup and UI responsiveness.
- Local cache is refreshed from shared snapshots.

## Public Sync APIs

From `Code.sync.service`:

- Status/revision: `check_shared_status`, `check_revision`, `sync_local_from_shared`
- Mutations: `create_equipment`, `update_equipment`, `delete_equipment`, `set_archived`, `toggle_verified`
- Imports: `run_excel_import`, `import_database_into_shared`
- Config helpers: `shared_sync_enabled`, `sync_interval_ms`, `shared_dir`, `shared_db_path`

## Operational States

`Shared sync disabled`
- Local-only behavior.
- No shared-path checks required.

`Shared available`
- Mutations/imports run against shared DB.
- Local cache is refreshed after shared writes.

`Shared unavailable`
- View/search still available from local cache.
- Mutations/import actions are disabled/gated.
- Status bar communicates disconnected state.

`Shared busy (locked)`
- Non-blocking busy messages.
- Retry behavior via timers/worker scheduling.

## Revision Semantics

- Revisions are numeric and stored in sync state.
- Shared revision increments on shared mutations/imports.
- Local cache stores revision after snapshot refresh.

## Path Resolution

- Shared root and DB paths resolve through runtime path helpers.
- `override_root` parameters allow tests or explicit path control.

## Compatibility Notes

- Legacy queue/tombstone DB APIs remain callable via `Code.db.database` facade.
- Current shared-first runtime does not depend on queue replay for normal flow.