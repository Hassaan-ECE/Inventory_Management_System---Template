# Testing Guide

## Dependency Layers

Runtime only:

```bash
pip install -r Lab_Template/requirements.txt
```

Development tests:

```bash
pip install -r requirements-dev.txt
```

## Test Types

- Smoke tests: app window/bootstrap against empty DB.
- Characterization tests: DB CRUD/search, snapshot behavior, sync states, main-window action routing.
- Targeted integration: import/sync flows that touch multiple modules.

## Primary Test Command

From `Lab_Template/`:

```bash
python -m pytest tests -q
```

## Suggested Local Workflow

1. Run focused test file while iterating.
2. Run full `tests/` before merge.
3. Run import/sync-related tests after changing `db`, `sync`, or `importer` modules.

## Common Issues

`pytest` missing
- Install `requirements-dev.txt`.

Qt plugin/display errors
- Ensure desktop session is available for PySide6 tests.
- Keep smoke tests minimal and avoid blocking dialogs in automated tests.

Workbook parser errors
- Ensure runtime deps (`openpyxl`, `xlrd`) are installed.
- Verify source workbook filenames configured in `app_config.py`.