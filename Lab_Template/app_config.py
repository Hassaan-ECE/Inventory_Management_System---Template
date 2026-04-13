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
    master_source_file: str
    survey_source_file: str
    excel_export_filename: str
    html_report_filename: str
    html_report_title: str
    database_label: str


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
    master_source_file="Master_Source.xlsx",
    survey_source_file="Survey_Source.xlsx",
    excel_export_filename="Lab_Inventory_Export.xlsx",
    html_report_filename="inventory_report.html",
    html_report_title="Lab Inventory Review",
    database_label="lab inventory database",
)
