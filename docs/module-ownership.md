# Module Ownership

## Shared Modules

`shared_core/Code/db`
- schema creation
- snapshot state (`sync_state`)
- equipment/import issue persistence
- local snapshot replacement helpers
- local cache read/write primitives used by shared-first sync

`shared_core/Code/gui`
- shared window shell
- add/edit dialog contracts
- quick-edit behavior
- search/filtering
- archive/verify/delete interaction
- disconnected view/search mode and edit/import enablement rules

`shared_core/Code/importer`
- workbook parsing
- merge/full import orchestration
- explicit import-to-db entry points for shared-connected operations

`shared_core/Code/sync`
- shared-first cache sync service
- worker-thread bridge for GUI calls
- revision/checkpoint checks
- shared reachability handling and local cache refresh behavior
- update manifest lookup

## Variant Modules

`ME_lab`
- active variant config
- ME workbook/source naming
- packaging metadata
- ME-focused tests

`TE_Lab`
- legacy reference config/tests

`Lab_Template`
- starter variant config/tests

## Boundary Rule

If a change affects more than one variant, it belongs in `shared_core` unless there is a concrete reason to keep it variant-specific.

## Shared Core Ownership Rule

- Any change to sync mechanics, local-cache refresh semantics, disconnected-mode UI behavior, or status-bar sync UX belongs under `shared_core/Code/`.
- Variants should only configure paths, flags, naming, and packaging metadata through `app_config.py` and variant-local build wiring.
