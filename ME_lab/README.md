# ME Lab Inventory

`ME_lab` is the Mechanical Engineering / machine shop variant of the shared desktop inventory system. This folder now contains a real app setup, not only planning notes.

## Folder Structure

```text
ME_lab/
|-- main.py
|-- app_config.py
|-- build.py
|-- requirements.txt
|-- README.md
|-- Machine_Shop_Inventory_System.txt
|-- App.png
|-- Data/
`-- tests/
```

## What Lives Here

- `main.py` launches the desktop app and triggers the first-run import when the database is empty.
- `app_config.py` defines the ME-specific identity, file names, table fields, feature flags, and export names.
- `build.py` packages the ME app into a Windows `.exe` with Nuitka, can build an installer, and can publish a release into the ME shared-drive folder structure.
- `Data/` holds the ME workbook and the local SQLite database used during source runs.
- `tests/` contains ME-focused regression tests for import, window behavior, and the add/edit dialog.
- `Machine_Shop_Inventory_System.txt` is the original requirement brief that guided the ME variant.

## Current ME Behavior

The ME app reuses `shared_core` for the database, GUI, import pipeline, search, and export logic, then layers ME-specific configuration on top.

Key ME settings today:

- source workbook: `Data/Machine Shop Material list.xlsx`
- database filename: `Data/me_lab_inventory.db` for source runs
- DB override env var: `ME_LAB_INVENTORY_DB_PATH`
- import profile: `me_single_workbook`
- survey workbook: not used for ME
- record images: enabled in the edit dialog
- project field: enabled in the edit dialog
- calibration-focused TE UI sections: disabled for ME

## Import Notes

The ME import path is based on a single workbook and reads all supported sheets through `shared_core/Code/importer/me_parser.py`.

Current schema-related behavior:

- `qty` is imported as a real numeric field
- `BOX No.` is preserved in record notes during import
- workbook picture values are preserved in record notes during import
- the dialog also supports a `picture_path` field for manually maintained record images

This means ME already supports the workflow, but `box number` is not yet a dedicated table/database field.

## Table And UI Defaults

The ME config currently declares these table fields:

- `asset_number`
- `qty`
- `manufacturer`
- `model`
- `description`
- `project_name`
- `location`
- `links`

`asset_number` and `project_name` are hidden by default in the table. The visible ME-first layout is centered on quantity, manufacturer, model, description, location, and links.

## Run Locally

```bash
cd ME_lab
pip install -r requirements.txt
python main.py
```

When the database is empty, startup imports from `Data/Machine Shop Material list.xlsx`. If you run a compiled build instead of source, the runtime prefers a `Data/` folder next to the executable when one exists.

## Tests

Run the ME test set with:

```bash
cd ME_lab
pip install pytest
python -m pytest tests -q
```

Current test coverage in this folder includes:

- ME single-workbook import behavior
- main window/table defaults
- add/edit dialog behavior for picture and project fields

## Build

Standard prerelease build:

```bash
cd ME_lab
python build.py
```

Build the current internal prerelease installer:

```bash
python build.py --version 0.9.0 --installer
```

Build and publish a shared release bundle:

```bash
python build.py --version 0.9.0 --installer --publish-shared --notes "Internal prerelease for ME shared-sync testing"
```

## Relationship To The Rest Of The Repo

- `shared_core/` is where reusable behavior should live.
- `TE_Lab/` is still the best reference when comparing against the older dual-workbook app flow.
- `Lab_Template/` is the clean base for spinning up new variants without copying old data or lab-specific behavior.
