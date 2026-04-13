# Lab Template

Starter app folder for a new inventory variant that reuses `shared_core`.

## Copy Workflow

1. Copy `Lab_Template` to a new app folder such as `ME_Lab`.
2. Update `app_config.py` with the new app name, env var, file names, and export names.
3. Add the expected source files into `Data/`.
4. Run `python main.py`.

## Included

- `main.py` for launching the desktop app
- `app_config.py` for app-specific naming and file configuration
- `build.py` for optional Nuitka `.exe` builds
- `requirements.txt` for runtime dependencies
- `tests/` as a small starter test scaffold
- `Data/` as the place for source files and the local SQLite database

## Notes

- The shared runtime logic lives in `../shared_core/Code/`.
- The app can still open with an empty database if the source files are not present yet.
- Rename the placeholder source file names in `app_config.py` before the first real import.
