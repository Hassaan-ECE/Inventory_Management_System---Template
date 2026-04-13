# Inventory Management System

Desktop inventory platform for managing multiple engineering team inventory apps from one shared codebase.

This repository started from a TE-only equipment manager and is now being organized into a reusable multi-team structure so future variants such as `ME_lab`, `IT_lab`, and others can share the same core code.

## Current Structure

```text
Inventory_Management_System/
├── shared_core/     # Shared database, importer, GUI, reporting, and utility code
├── TE_Lab/          # Current working TE inventory app
├── ME_lab/          # ME / machine shop planning notes and future app folder
├── IT_lab/          # Reserved for a future IT variant
└── Lab_Template/    # Reusable starter app folder for new variants
```

## Repository Goals

- keep one shared runtime for database, import, GUI, export, and reporting logic
- keep each lab app small and focused on its own naming, source files, and special rules
- make it easy to create a new lab variant without copying random old outputs or caches
- support both local source execution and optional Windows `.exe` builds

## Shared Core

`shared_core/Code/` contains the reusable application logic:

- `db/` for SQLite schema, models, CRUD, and search
- `gui/` for the PySide6 desktop UI
- `importer/` for Excel parsing and import pipelines
- `reporting/` for HTML report generation
- `utils/` for export helpers and runtime path handling

## Current App Status

### `TE_Lab`

`TE_Lab` is the current working reference app.

It includes:

- the real app entry point
- app-specific configuration
- source Excel files and local database in `Data/`
- build script for creating a Windows executable
- regression tests

Run it with:

```bash
cd TE_Lab
pip install -r requirements.txt
python main.py
```

### `ME_lab`

`ME_lab` currently contains the planning brief for the machine shop / mechanical engineering version of the app.

See:

- [ME_lab/README.md](ME_lab/README.md)
- [ME_lab/Machine_Shop_Inventory_System.txt](ME_lab/Machine_Shop_Inventory_System.txt)

### `Lab_Template`

`Lab_Template` is the clean starter folder for new app variants.

Use it when creating a new lab app so `TE_Lab` can remain a real implementation instead of becoming the template.

## Creating A New Lab App

1. Copy `Lab_Template` to a new folder such as `ME_lab` or `IT_lab`.
2. Update `app_config.py` with the new app name, file names, export names, and DB environment variable.
3. Put the expected source files into that app's `Data/` folder.
4. Run `python main.py`.
5. Add any lab-specific parsing or UI behavior only if it truly cannot stay in `shared_core`.

## Python Dependencies

Current app dependencies:

- `PySide6`
- `pandas`
- `openpyxl`
- `xlrd`

Install from an app folder such as `TE_Lab/` or `Lab_Template/`:

```bash
pip install -r requirements.txt
```

## Build Support

App folders can include a `build.py` script for optional Nuitka-based Windows executable builds.

The current working example is:

- [TE_Lab/build.py](TE_Lab/build.py)

The generic starter is:

- [Lab_Template/build.py](Lab_Template/build.py)

## Notes

- This repository is intended to be the new shared multi-team home for the inventory system.
- The older TE-only repo can remain as the historical single-app version.
- Generated files such as `__pycache__`, build outputs, and local scratch artifacts should stay out of version control.
