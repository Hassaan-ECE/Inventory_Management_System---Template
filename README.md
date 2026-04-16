# Inventory Management System

Shared desktop inventory system for multiple engineering teams built on one reusable `shared_core` codebase.

Current development is centered on `ME_lab`. `TE_Lab` is still in the repo as the reference implementation for the older dual-workbook flow, and `Lab_Template` remains the clean starting point for future variants.

## Repository Layout

```text
Inventory_Management_System/
|-- shared_core/    # Shared database, GUI, importer, reporting, and utility code
|-- ME_lab/         # Active ME / machine shop variant
|-- TE_Lab/         # TE reference app
`-- Lab_Template/   # Starter app folder for new variants
```

## How The Codebase Is Split

- `shared_core/Code/` owns the reusable runtime: SQLite models, import pipeline, PySide6 GUI, export helpers, and reporting.
- Each app folder owns the variant-specific config in `app_config.py`, local `Data/`, build script, and tests.
- `ME_lab` uses a single-workbook import profile.
- `TE_Lab` uses the older master-plus-survey import flow.

## ME Version At A Glance

`ME_lab` is no longer just a planning folder. It now contains:

- a runnable entry point in `ME_lab/main.py`
- ME-specific app metadata in `ME_lab/app_config.py`
- the source workbook `ME_lab/Data/Machine Shop Material list.xlsx`
- the local ME database `ME_lab/Data/me_lab_inventory.db`
- ME regression tests in `ME_lab/tests/`
- a Nuitka build script in `ME_lab/build.py`
- the original requirements notes in `ME_lab/Machine_Shop_Inventory_System.txt`

The ME variant currently enables:

- single-workbook import via `import_profile="me_single_workbook"`
- quantity-focused table views
- project and record-image support in the edit workflow
- Excel and HTML export configuration

Current implementation note:

- workbook values such as `BOX No.` and workbook picture references are preserved during import, but they are not first-class ME schema columns yet; they are flattened into record notes during import.

## Run The ME App

```bash
cd ME_lab
pip install -r requirements.txt
python main.py
```

On first launch, if the ME database is empty, the app imports data from `Data/Machine Shop Material list.xlsx`.

## Test And Build ME

```bash
cd ME_lab
pip install pytest
python -m pytest tests -q
python build.py
```

`build.py` creates a Windows executable with Nuitka and packages the app `Data/` folder plus shared GUI assets.

## Notes

- `TE_Lab` is still useful as the most mature reference implementation when shared-core behavior needs comparison.
- `Lab_Template` should be the base for future variants instead of copying a working lab folder wholesale.
- Search, database behavior, exports, and most UI logic live in `shared_core`, so cross-variant changes usually belong there.
