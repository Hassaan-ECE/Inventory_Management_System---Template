"""Central application metadata for a reusable inventory app variant."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Small set of values that distinguish one inventory app variant from another."""

    app_dir_name: str
    display_name: str
    application_name: str
    company_name: str
    product_name: str
    file_description: str
    db_filename: str
    db_path_env_var: str
    build_exe_name: str
    installer_exe_name: str
    installer_app_id: str
    master_source_file: str
    survey_source_file: str
    import_profile: str
    show_calibration_section: bool
    enable_record_images: bool
    enable_project_field: bool
    show_age_search_actions: bool
    default_hidden_table_fields: tuple[str, ...]
    record_label: str
    table_fields: tuple[str, ...]
    filter_fields: tuple[str, ...]
    excel_export_filename: str
    html_report_filename: str
    html_report_title: str
    database_label: str
    app_version: str
    shared_network_root: str
    shared_db_filename: str
    release_manifest_filename: str
    auto_sync_interval_ms: int
    enable_shared_sync: bool
    enable_update_checks: bool


APP_CONFIG = AppConfig(
    app_dir_name="Lab_Inventory_Template",
    display_name="Lab Inventory",
    application_name="Lab Inventory Manager",
    company_name="Your Team",
    product_name="Lab Inventory",
    file_description="Lab Inventory Manager",
    db_filename="lab_inventory.db",
    db_path_env_var="LAB_INVENTORY_DB_PATH",
    build_exe_name="Lab_Inventory.exe",
    installer_exe_name="Lab_Inventory_Setup.exe",
    installer_app_id="{42866E6C-0F7F-4F3B-B788-61C271D4A164}",
    master_source_file="Master_Source.xlsx",
    survey_source_file="Survey_Source.xlsx",
    import_profile="te_dual_workbook",
    show_calibration_section=True,
    enable_record_images=False,
    enable_project_field=False,
    show_age_search_actions=True,
    default_hidden_table_fields=(),
    record_label="Equipment",
    table_fields=(
        "asset_number",
        "manufacturer",
        "model",
        "description",
        "estimated_age_years",
        "lifecycle_status",
        "working_status",
        "calibration_status",
        "location",
    ),
    filter_fields=(
        "asset_number",
        "manufacturer",
        "model",
        "description",
        "estimated_age_years",
        "lifecycle_status",
        "working_status",
        "calibration_status",
        "location",
    ),
    excel_export_filename="Lab_Inventory_Export.xlsx",
    html_report_filename="inventory_report.html",
    html_report_title="Lab Inventory Review",
    database_label="lab inventory database",
    app_version="1.0.0",
    shared_network_root="",
    shared_db_filename="",
    release_manifest_filename="current.json",
    auto_sync_interval_ms=300000,
    enable_shared_sync=False,
    enable_update_checks=False,
)
