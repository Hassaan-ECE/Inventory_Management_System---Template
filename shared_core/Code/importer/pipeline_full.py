"""Full-import orchestration and explicit strategy dispatch."""

from __future__ import annotations

from pathlib import Path

from Code.importer._pipeline_impl import (
    _emit,
    _import_profile,
    _resolve_target_db_path,
    run_full_import as _run_full_import_impl,
    run_full_import_to_db as _run_full_import_to_db_impl,
)

_FULL_IMPORT_STRATEGY_RUNNERS = {
    "single_workbook": _run_full_import_impl,
    "dual_workbook": _run_full_import_impl,
}


def _normalize_full_import_strategy(strategy: str | None) -> str:
    normalized = (strategy or "").strip().lower()
    if not normalized:
        return "single_workbook" if _import_profile() == "me_single_workbook" else "dual_workbook"
    if normalized in _FULL_IMPORT_STRATEGY_RUNNERS:
        return normalized
    raise ValueError(f"Unsupported full-import strategy: {strategy}")


def run_full_import(
    data_dir: Path,
    db_path: Path | None = None,
    progress_callback=None,
    *,
    target_db_path: Path | str | None = None,
    use_wal: bool = True,
    strategy: str | None = None,
) -> dict:
    """Run a full import with explicit strategy selection."""
    normalized_strategy = _normalize_full_import_strategy(strategy)
    runner = _FULL_IMPORT_STRATEGY_RUNNERS[normalized_strategy]
    return runner(
        data_dir=data_dir,
        db_path=db_path,
        progress_callback=progress_callback,
        target_db_path=target_db_path,
        use_wal=use_wal,
    )


def run_full_import_to_db(
    data_dir: Path,
    target_db_path: Path | str,
    progress_callback=None,
    *,
    use_wal: bool = False,
    strategy: str | None = None,
) -> dict:
    """Run a full import against an explicit database path."""
    normalized_strategy = _normalize_full_import_strategy(strategy)
    if normalized_strategy not in _FULL_IMPORT_STRATEGY_RUNNERS:
        raise ValueError(f"Unsupported full-import strategy: {normalized_strategy}")
    return _run_full_import_to_db_impl(
        data_dir=data_dir,
        target_db_path=target_db_path,
        progress_callback=progress_callback,
        use_wal=use_wal,
    )


__all__ = [
    "_emit",
    "_import_profile",
    "_normalize_full_import_strategy",
    "_resolve_target_db_path",
    "run_full_import",
    "run_full_import_to_db",
]
