# Lab Template

`Lab_Template` is the thin app wrapper around `shared_core`.

Use it as the starting point for a new inventory variant while keeping shared runtime behavior in `shared_core/Code`.

## What Lives Here

- `main.py` - application entrypoint (`main()`)
- `app_config.py` - variant metadata and behavior flags
- `build.py` - optional packaging/build helper
- `requirements.txt` - runtime dependencies only
- `tests/` - smoke + characterization tests for template behavior

## Create a New Variant

1. Copy `Lab_Template` to your target variant folder.
2. Update `app_config.py` values (names, filenames, shared-sync options).
3. Add source files to `Data/` based on your import profile.
4. Run `python main.py`.

## Development Commands

From `Lab_Template/`:

```bash
pip install -r requirements.txt
pip install -r ..\requirements-dev.txt
python -m pytest tests -q
python main.py
python build.py
```

## First-Run Import Behavior

- If expected source files are present, first launch runs an import.
- If files are missing, the app still starts against an empty DB and shows guidance.
- You can run imports later from the app UI.

## Customization Safety Rules

- Keep business/runtime logic changes in `shared_core/Code`.
- Keep variant-specific naming, paths, and flags in `app_config.py`.
- Do not rename existing `AppConfig` keys if backward compatibility is required.