"""Central application metadata for the ME lab inventory variant."""

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
    app_dir_name="ME_Lab_Inventory",
    display_name="ME Lab Inventory",
    application_name="ME Lab Inventory Manager",
    company_name="ME Lab Inventory",
    product_name="ME Lab Inventory",
    file_description="ME Lab Inventory Manager",
    db_filename="me_lab_inventory.db",
    db_path_env_var="ME_LAB_INVENTORY_DB_PATH",
    build_exe_name="ME_Lab_Inventory.exe",
    master_source_file="Machine Shop Material list.xlsx",
    survey_source_file="",
    import_profile="me_single_workbook",
    show_calibration_section=False,
    enable_record_images=True,
    enable_project_field=True,
    show_age_search_actions=False,
    default_hidden_table_fields=("asset_number", "project_name"),
    record_label="Record",
    table_fields=("asset_number", "qty", "manufacturer", "model", "description", "project_name", "location", "links"),
    filter_fields=("asset_number", "manufacturer", "model", "description", "location"),
    excel_export_filename="ME_Lab_Inventory_Export.xlsx",
    html_report_filename="me_lab_inventory_report.html",
    html_report_title="ME Lab Inventory Review",
    database_label="ME Lab inventory database",
    app_version="1.0.0",
    shared_network_root=r"S:\Manufacturing\Internal\_Syed_H_Shah\InventoryApps\ME",
    shared_db_filename="me_lab_shared.db",
    release_manifest_filename="current.json",
    auto_sync_interval_ms=300000,
    enable_shared_sync=True,
    enable_update_checks=True,
)
