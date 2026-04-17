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

## Latest Code Review (2026-04-17)

### Findings

- High: `AddEditDialog` currently resets several ME-specific fields during save in edit mode.
  - File: `shared_core/Code/gui/add_edit_dialog.py`
  - In ME layout save handling, lifecycle, working status, estimated age, and calibration fields are force-set to defaults even when editing existing records.
- Medium: `Equipment.add_source_ref` appends source references without deduplication.
  - File: `shared_core/Code/db/models.py`
  - Re-running imports can duplicate identical source refs in the same record.
- Medium: Survey import parsing is brittle to column-order changes.
  - File: `shared_core/Code/importer/survey_parser.py`
  - Fixed-position column mapping can silently mis-read rows when source headers change.
- Low/Maintainability: app startup/build scripts are duplicated across variants.
  - Files: `ME_lab/main.py`, `TE_Lab/main.py`, `Lab_Template/main.py`, and their `build.py` counterparts.
  - Consider consolidating shared bootstrap/build behavior into `shared_core` helper modules.

### Recommended implementation order

1. Fix ME edit-save behavior so existing lifecycle/working/calibration/age values are preserved unless explicitly changed.
2. Deduplicate source references in `Equipment.add_source_ref` (or during importer merge writeback).
3. Refactor survey parsing to use header-aware column mapping with fallback aliases.
4. Extract shared launcher/build scaffolding once all behavior is validated.
