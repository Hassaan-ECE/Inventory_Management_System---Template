# Inventory Management System

Desktop inventory variants built on one shared runtime in `shared_core`.

`ME_lab` is the active variant. `TE_Lab` remains as a legacy reference for the older workbook flow, and `Lab_Template` is the starting point for future variants.

## Repository Layout

```text
Inventory_Management_System/
|-- shared_core/    # Runtime code (db, gui, import, sync, reporting)
|-- ME_lab/         # Active ME variant (thin app wrapper/config/tests/build)
|-- TE_Lab/         # Legacy reference variant
`-- Lab_Template/   # Starter structure for new variants
```

## Ownership Model

- `shared_core/Code/` owns runtime behavior, including schema, importers, UI mechanics, search, exports, shared-db sync, and update checks.
- Variant folders (`ME_lab`, `TE_Lab`, future labs) should stay thin and own only:
  - `app_config.py` and variant metadata
  - local `Data/` seed files
  - packaging/release wiring (`build.py`, installer naming, shared root values)
  - variant-focused tests and docs
- Cross-variant behavior changes should default to `shared_core`, not per-variant forks.

## Shared-First Sync Model

- One shared SQLite database is the source of truth for each variant.
- Each source folder keeps its own local SQLite cache for fast startup, view, and search.
- Running two copied source folders on one PC is supported: each folder keeps its own local `Data/*.db` file while both can point at the same shared DB.
- Background sync refreshes local cache from shared; runtime does not use outbox/offline queues, tombstones, or `sync.lock`.
- Connected edits/imports target authoritative shared state and refresh local cache.
- If shared storage is unavailable, the app remains open in view/search mode only with edits/imports disabled.
- Background sync loss is communicated in the status bar; no modal popup is shown for disconnect state.

Detailed notes are documented in:

- [docs/shared-sync-authoritative.md](docs/shared-sync-authoritative.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/module-ownership.md](docs/module-ownership.md)
- [docs/migration-notes.md](docs/migration-notes.md)

## Run, Test, and Build ME

```bash
cd ME_lab
pip install -r requirements.txt
python main.py
python -m pytest tests -q
python build.py
```

On first launch with an empty local DB, ME imports from `Data/Machine Shop Material list.xlsx`.
