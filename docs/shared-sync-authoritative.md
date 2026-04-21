# Shared-First Authoritative Sync Model

File name note: this path is preserved for link stability.

## Purpose

Define the runtime contract where one shared database is authoritative and each source folder holds a local cache.

## Storage Topology

- Each source folder has its own local cache DB.
- The authoritative DB is `<shared_root>/shared/<shared_db_filename>`.
- Multiple local source copies on one machine are supported; each keeps its own local cache.

## Runtime Expectations

- Shared DB is source of truth when shared sync is enabled.
- Local DB is cache for startup/view/search responsiveness.
- Runtime does not rely on outbox replay or lock-file choreography for current shared-first flow.
- Edit/import actions are available only while shared is reachable in shared-sync mode.
- Disconnected mode remains open for view/search only.
- Background sync loss is communicated through status bar messaging.

## Ownership Boundaries

- `Code/sync/` owns shared reachability checks, revision checks, and cache refresh behavior.
- `Code/db/` owns schema and snapshot copy/replace primitives.
- `Lab_Template/app_config.py` owns path/flag configuration only.

## Testing Expectations

- Verify shared snapshot refresh updates local cache correctly.
- Verify unavailable/busy states produce non-blocking status behavior.
- Verify mutation paths refresh local cache after shared writes.
- Keep legacy queue/tombstone APIs callable for compatibility checks where needed.