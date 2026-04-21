# Getting Started

## Prerequisites

- Python 3.11+ (3.12 recommended)
- `pip`
- Windows desktop environment (PySide6 GUI)

## Install Dependencies

From `Lab_Template/`:

```bash
pip install -r requirements.txt
pip install -r ..\\requirements-dev.txt
```

## Run the App

```bash
python main.py
```

## Run Tests

```bash
python -m pytest tests -q
```

## First Launch Behavior

- The app initializes local SQLite tables.
- If configured source files are present, first-run import can populate data.
- If files are missing, the app still opens against an empty DB.

## Common Troubleshooting

`No module named PySide6`
- Re-run `pip install -r requirements.txt` in the same interpreter environment.

`No module named pytest`
- Install dev dependencies with `pip install -r ..\\requirements-dev.txt`.

App opens but shared sync actions stay disabled
- Check `app_config.py` shared settings (`enable_shared_sync`, `shared_network_root`, `shared_db_filename`).
- Confirm shared root exists and is reachable.

Import errors for workbook files
- Confirm workbook names in `app_config.py` match files in `Data/`.
- Ensure `openpyxl`/`xlrd` are installed from runtime requirements.