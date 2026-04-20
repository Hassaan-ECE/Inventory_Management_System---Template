# ME Lab Inventory

`ME_lab` is the Mechanical Engineering / machine shop variant built on the shared runtime in `shared_core`.

## Folder Scope

```text
ME_lab/
|-- main.py
|-- app_config.py
|-- build.py
|-- requirements.txt
|-- README.md
|-- Machine_Shop_Inventory_System.txt
|-- Data/
`-- tests/
```

This folder is intentionally thin:

- `main.py` wires startup into shared runtime behavior.
- `app_config.py` defines ME-specific identity, fields, feature flags, shared paths, and release names.
- `build.py` handles packaging/publishing for this variant.
- `tests/` covers variant behavior and integration points.
- Runtime behavior (db/gui/import/sync/update logic) is owned by `shared_core`.

## Shared-First Sync Model (ME)

- The ME shared DB path (`shared/<shared_db_filename>`) is authoritative for team state.
- Each ME source copy keeps its own local cache DB to support startup and search performance.
- Running two ME source folders side by side is supported: each folder keeps its own `Data/me_lab_inventory.db` cache while both can target the same shared ME DB.
- Runtime sync updates local cache from shared and does not rely on outbox/offline queue replay.
- Runtime sync no longer depends on tombstones or `sync.lock`.
- When shared storage is disconnected, the UI stays available for view/search only; edit/import actions are disabled.
- Disconnect state is status-bar only; background sync loss does not trigger a modal popup.

Detailed docs:

- [../docs/shared-sync-authoritative.md](../docs/shared-sync-authoritative.md)
- [../docs/architecture.md](../docs/architecture.md)
- [../docs/module-ownership.md](../docs/module-ownership.md)

## Current ME Configuration Highlights

- app version: `0.9.3`
- source workbook: `Data/Machine Shop Material list.xlsx`
- import profile: `me_single_workbook`
- local DB filename: `me_lab_inventory.db`
- DB override env var: `ME_LAB_INVENTORY_DB_PATH`
- shared release root: `S:\Manufacturing\Internal\_Syed_H_Shah\InventoryApps\ME`
- release manifest: `current.json`
- record images: enabled
- project field: enabled
- calibration-focused sections: disabled

## Import and UI Notes

- ME imports a single workbook through `shared_core/Code/importer/me_parser.py`.
- `qty` is a first-class numeric field.
- `BOX No.` and workbook picture values are currently preserved in notes.
- `picture_path` remains available for manually managed record images.
- Default ME table fields are: `asset_number`, `qty`, `manufacturer`, `model`, `description`, `project_name`, `location`, `links`.
- Import actions require shared connectivity and are disabled while disconnected.

## Run, Test, Build

```bash
cd ME_lab
pip install -r requirements.txt
python main.py
python -m pytest tests -q
python build.py
```

Build and publish a shared release bundle:

```bash
python build.py --version 0.9.3 --installer --publish-shared --notes "Internal prerelease"
```

Useful build flags:

- `--jobs 1`
- `--release-root <path>`
- `--sign`
- `--allow-version-mismatch` (only when intentionally diverging from `app_config.py`)
