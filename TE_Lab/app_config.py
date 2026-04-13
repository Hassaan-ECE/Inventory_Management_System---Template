"""Central application metadata for shared-core and team-specific variants."""

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
    app_dir_name="TE_Lab_Equipment",
    display_name="TE Lab Equipment",
    application_name="TE Lab Equipment Inventory Manager",
    company_name="TE Lab Equipment",
    product_name="TE Lab Equipment",
    file_description="TE Lab Equipment Inventory Manager",
    db_filename="lab_equipment.db",
    db_path_env_var="TE_LAB_EQUIPMENT_DB_PATH",
    build_exe_name="TE_Lab_Equipment.exe",
    master_source_file="Master List of Eng.Equipment - All - 2020.RO.xls",
    survey_source_file="Survey oF Equip In Eng Lab.xlsx",
    excel_export_filename="TE_Lab_Equipment_Export.xlsx",
    html_report_filename="verified_equipment_report.html",
    html_report_title="TE Lab Test Equipment Age Review",
    database_label="TE Lab Equipment database",
)
