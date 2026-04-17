# ME Lab Inventory

`ME_lab` is the Mechanical Engineering / machine shop variant of the shared desktop inventory system. This folder now contains a real app setup, not only planning notes.

Built and maintained by `Syed Hassaan Shah`.

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

- current internal prerelease version: `0.9.0`
- builder / publisher: `Syed Hassaan Shah`
- source workbook: `Data/Machine Shop Material list.xlsx`
- database filename: `Data/me_lab_inventory.db` for source runs
- DB override env var: `ME_LAB_INVENTORY_DB_PATH`
- import profile: `me_single_workbook`
- survey workbook: not used for ME
- record images: enabled in the edit dialog
- project field: enabled in the edit dialog
- calibration-focused TE UI sections: disabled for ME

The ME app is now local-first:

- each installed computer uses its own local SQLite database
- the shared ME workspace holds the canonical shared database plus release artifacts
- startup and background sync try to merge local and shared changes when it is safe to do so
- app updates are driven by the shared `current.json` release manifest

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

## Shared Release Layout

The current shared ME release root is:

```text
S:\Manufacturing\Internal\_Syed_H_Shah\InventoryApps\ME
```

Expected layout:

```text
ME\
|-- current.json
|-- backups\
|-- releases\
|   `-- 0.9.0\
|       |-- ME_Lab_Inventory.exe
|       |-- ME_Lab_Inventory_Setup.exe
|       |-- release.json
|       `-- release_notes.txt
`-- shared\
    `-- me_lab_shared.db
```

Notes:

- `current.json` tells installed clients which installer is the current release
- `current.json` and `release.json` include `built_by` / `publisher` metadata for `Syed Hassaan Shah`
- `shared\me_lab_shared.db` is created automatically once the shared-sync path is used
- `backups\` stores shared DB snapshots before shared writes
- `releases\<version>\` stores the published installer, raw exe, and release metadata

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

Useful build flags:

- `--jobs 1` keeps Nuitka on a single compile job and is safer on lower-memory laptops
- `--release-root <path>` publishes to a different shared root than the one in `app_config.py`
- `--sign` signs the built exe and installer when the code-signing environment variables are configured

Build branding notes:

- rebuilt executables embed the shared app icon from `shared_core/assets/app_icon.ico`
- rebuilt installers use the same shared icon for the installer shell
- rebuilt executables and installers use `Syed Hassaan Shah` as the publisher / builder attribution

## Install And Remove

Install the app from the published installer:

```text
S:\Manufacturing\Internal\_Syed_H_Shah\InventoryApps\ME\releases\0.9.0\ME_Lab_Inventory_Setup.exe
```

The installer places the app in the user profile and registers a normal Windows uninstall entry.

The built executable and installer metadata use `Syed Hassaan Shah` as the publisher / builder attribution.

Uninstall behavior:

- uninstall removes the installed program files
- uninstall does not delete the local user database under `%LOCALAPPDATA%\ME_Lab_Inventory\` by default
- preserving the local database is intentional so an uninstall does not silently remove inventory data

## Relationship To The Rest Of The Repo

- `shared_core/` is where reusable behavior should live.
- `TE_Lab/` is still the best reference when comparing against the older dual-workbook app flow.
- `Lab_Template/` is the clean base for spinning up new variants without copying old data or lab-specific behavior.
