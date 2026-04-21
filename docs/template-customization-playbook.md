# Template Customization Playbook

This guide explains every `AppConfig` field in `Lab_Template/app_config.py` and where each value matters.

## Workflow

1. Copy `Lab_Template` to your variant folder.
2. Update `APP_CONFIG` values.
3. Add source files to `Data/`.
4. Run app + tests.
5. Only then customize deeper runtime behavior in `shared_core/Code` if required.

## App Identity

- `app_dir_name`: Folder identifier for this variant.
- `display_name`: Primary UI title text.
- `application_name`: OS/process-facing app name.
- `company_name`: Build metadata/company label.
- `product_name`: Build metadata/product label.
- `file_description`: Build metadata/description.
- `creator_name`: Optional credit/owner label.

## Database + Paths

- `db_filename`: Local cache DB filename.
- `db_path_env_var`: Environment variable override for local DB path.
- `database_label`: User-facing DB label in messages.

## Build/Installer Naming

- `build_exe_name`: Generated executable file name.
- `installer_exe_name`: Installer output file name.
- `installer_app_id`: Stable installer app GUID.
- `app_version`: Version string shown/released.

## Import Source Configuration

- `master_source_file`: Primary workbook filename.
- `survey_source_file`: Survey workbook filename (if dual-workbook profile).
- `import_profile`:
  - `te_dual_workbook` for master+survey flow.
  - `me_single_workbook` for single-workbook flow.

## UI/Feature Flags

- `show_calibration_section`: Show calibration fields in dialogs.
- `enable_record_images`: Enable record image fields/preview.
- `enable_project_field`: Enable project-name field.
- `show_age_search_actions`: Show age-specific search shortcuts.

## Table/Search Presentation

- `record_label`: Label used for record nouns in UI buttons/messages.
- `table_fields`: Ordered columns shown in the table.
- `filter_fields`: Enabled search/filter fields.
- `default_hidden_table_fields`: Columns hidden by default.

## Export/Report Output

- `excel_export_filename`: Default Excel export filename.
- `html_report_filename`: Default HTML report filename.
- `html_report_title`: HTML report title.

## Shared Sync + Updates

- `shared_network_root`: Shared root folder path (if used).
- `shared_db_filename`: Shared authoritative DB filename.
- `release_manifest_filename`: Update manifest filename (for update checks).
- `auto_sync_interval_ms`: Periodic sync interval in ms.
- `enable_shared_sync`: Enable shared-first sync mode.
- `enable_update_checks`: Enable startup update checks.

## Safe Customization Rules

- Keep key names unchanged for compatibility.
- Prefer changing values, not removing fields.
- Put cross-variant behavior changes in `shared_core/Code`, not variant wrappers.
- Keep `db_filename` and `shared_db_filename` distinct.

## Validation Checklist

- App starts with empty DB.
- Import works for chosen profile.
- Search/table fields align with configured fields.
- Export file names and report title match expected branding.
- Shared sync flags behave as intended (disabled/local-only vs shared-first).