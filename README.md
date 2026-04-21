# Inventory Management System Template

This repository is a starter template for building lab-inventory desktop variants on a shared runtime.

The codebase is intentionally trimmed to:

- `Lab_Template/` - thin app wrapper you copy/rename for a new variant
- `shared_core/` - reusable runtime (db, GUI, importer, sync, reporting)
- `docs/` - architecture, operations, customization, and maintenance references

## Repository Layout

```text
Inventory_Management_System - Template/
|-- Lab_Template/          # Thin variant wrapper: config, launcher, build, tests
|-- shared_core/           # Shared runtime used by all variants
|   `-- Code/
|       |-- db/            # DB schema/repos/snapshot and compatibility facade
|       |-- gui/           # Main window + dialogs + UI helpers
|       |-- importer/      # Full/merge import orchestration + parsers
|       |-- sync/          # Shared-first sync service + worker bridge
|       |-- reporting/     # HTML report generation
|       `-- utils/         # Runtime paths, exports, field utilities
`-- docs/                  # Template playbooks and runtime references
```

## Quick Start

1. Install runtime dependencies:

```bash
cd Lab_Template
pip install -r requirements.txt
```

2. Run the app:

```bash
python main.py
```

3. Run tests (from `Lab_Template/`):

```bash
pip install -r ..\requirements-dev.txt
python -m pytest tests -q
```

## Compatibility Guarantees

- `Lab_Template/main.py` keeps `main()` as the entrypoint.
- `shared_core/Code/db/database.py` remains the public DB import surface.
- `shared_core/Code/sync/service.py` remains the public sync import surface.
- Existing `AppConfig` keys remain backward compatible.

## Documentation Index

- [Getting Started](docs/getting-started.md)
- [Template Customization Playbook](docs/template-customization-playbook.md)
- [Code Map](docs/code-map.md)
- [Sync Runtime Reference](docs/sync-runtime-reference.md)
- [Testing Guide](docs/testing-guide.md)
- [Maintenance Guide](docs/maintenance-guide.md)
- [Architecture](docs/architecture.md)
- [Module Ownership](docs/module-ownership.md)
- [Migration Notes](docs/migration-notes.md)
- [Shared Sync Authoritative Model](docs/shared-sync-authoritative.md)