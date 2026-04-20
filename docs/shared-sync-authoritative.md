# Shared-First Authoritative Sync Model

File name note: this path is preserved for link stability.

## Purpose

Define the runtime contract where one shared database is authoritative and each source folder holds a local cache.

## Storage Topology

- Each source folder has its own local cache DB (resolved from runtime path rules and optional env override).
- Two copied source folders on the same machine are a supported workflow; each keeps its own local cache while sharing the same authoritative DB.
- The authoritative DB for the variant is `<shared_root>/shared/<shared_db_filename>`.
- Variant folders provide configuration only; sync behavior is owned by `shared_core`.

## Ownership Boundaries

- `shared_core/Code/sync/` owns shared reachability checks, cache refresh behavior, and status reporting.
- `shared_core/Code/db/` owns schema and snapshot/copy primitives used to keep local cache aligned to shared.
- Variant folders (`ME_lab`, future labs) own only config values for shared root and DB filenames.

## Runtime Expectations

- Shared DB is the single source of truth.
- Local DB is a cache copy used for startup, view, and search responsiveness.
- Runtime does not depend on outbox/offline queues, tombstones, or `sync.lock`.
- Edit/import operations are available only while shared is connected.
- Disconnected mode remains open for view/search only; edit/import entry points are disabled.
- Background sync loss is communicated through status bar messaging (no modal popup for disconnect state).
- Update checks remain driven by shared release manifests (for example `current.json`).

## Test Migration Guidelines

- Assert that shared snapshot state populates/refreshes local cache.
- Assert that shared state remains authoritative over divergent local cache rows.
- Remove assertions about queue replay, outbox counts, tombstone propagation, and lock-file behavior.
- Add UI assertions that disconnected mode is view/search only with edit/import actions disabled.
- Add UI assertions that background sync loss does not trigger modal popup warnings.
