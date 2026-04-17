"""Nuitka build and release script for the ME inventory app.

Usage:
    python build.py
    python build.py --version 0.9.0
    python build.py --installer
    python build.py --installer --publish-shared
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from app_config import APP_CONFIG

REPO_ROOT = Path(__file__).resolve().parent
SHARED_ROOT = REPO_ROOT.parent / "shared_core"
SHARED_ASSETS_DIR = SHARED_ROOT / "Code" / "gui" / "assets"
VENV_DIR = REPO_ROOT / ".venv312"
OUTPUT_DIR = REPO_ROOT / "Output"
INSTALLER_SCRIPT = REPO_ROOT / "installer.iss"
EXE_NAME = APP_CONFIG.build_exe_name
INSTALLER_NAME = APP_CONFIG.installer_exe_name
PYTHON_VERSION = "3.12"
DEFAULT_VERSION = APP_CONFIG.app_version


def find_python() -> Path | None:
    python_exe = VENV_DIR / "Scripts" / "python.exe"
    if python_exe.exists():
        return python_exe
    return None


def create_venv() -> Path:
    print(f"Creating Python {PYTHON_VERSION} virtual environment at {VENV_DIR} ...")
    result = subprocess.run(
        ["py", f"-{PYTHON_VERSION}", "-m", "venv", str(VENV_DIR)],
        check=False,
    )
    if result.returncode != 0:
        sys.exit(f"Failed to create virtual environment. Is Python {PYTHON_VERSION} installed?")
    return VENV_DIR / "Scripts" / "python.exe"


def install_deps(python_exe: Path) -> None:
    print("Installing build dependencies ...")
    result = subprocess.run(
        [
            str(python_exe),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "setuptools",
            "wheel",
            "nuitka",
            "ordered-set",
            "zstandard",
            "-r",
            str(REPO_ROOT / "requirements.txt"),
        ],
        check=False,
    )
    if result.returncode != 0:
        sys.exit("Failed to install build dependencies.")


def find_signtool() -> Path | None:
    which = shutil.which("signtool.exe")
    if which:
        return Path(which)

    sdk_root = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Windows Kits" / "10" / "bin"
    if sdk_root.exists():
        candidates = sorted(sdk_root.rglob("signtool.exe"), reverse=True)
        if candidates:
            return candidates[0]

    return None


def sign_binary(binary_path: Path) -> None:
    signtool = find_signtool()
    if not signtool:
        sys.exit("signtool.exe not found. Install the Windows SDK or remove --sign.")

    if not binary_path.exists():
        sys.exit(f"Expected binary not found at {binary_path}")

    pfx_path = os.environ.get("CODE_SIGN_PFX_PATH", "")
    pfx_password = os.environ.get("CODE_SIGN_PFX_PASSWORD", "")
    subject_name = os.environ.get("CODE_SIGN_SUBJECT_NAME", "")

    if pfx_path:
        if not pfx_password:
            sys.exit("CODE_SIGN_PFX_PASSWORD is required when CODE_SIGN_PFX_PATH is set.")
        cmd = [
            str(signtool),
            "sign",
            "/fd",
            "SHA256",
            "/td",
            "SHA256",
            "/tr",
            "https://timestamp.digicert.com",
            "/f",
            pfx_path,
            "/p",
            pfx_password,
            str(binary_path),
        ]
    elif subject_name:
        cmd = [
            str(signtool),
            "sign",
            "/fd",
            "SHA256",
            "/td",
            "SHA256",
            "/tr",
            "https://timestamp.digicert.com",
            "/n",
            subject_name,
            str(binary_path),
        ]
    else:
        sys.exit(
            "Set CODE_SIGN_PFX_PATH/CODE_SIGN_PFX_PASSWORD or CODE_SIGN_SUBJECT_NAME "
            "before using --sign."
        )

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        sys.exit(f"Code signing failed for {binary_path.name}.")


def build(python_exe: Path, version: str, jobs: int) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    build_env = os.environ.copy()
    existing_pythonpath = build_env.get("PYTHONPATH", "").strip()
    build_env["PYTHONPATH"] = (
        f"{SHARED_ROOT}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(SHARED_ROOT)
    )

    nuitka_args = [
        str(python_exe),
        "-m",
        "nuitka",
        "--mode=onefile",
        "--mingw64",
        "--assume-yes-for-downloads",
        "--enable-plugin=pyside6",
        "--windows-console-mode=disable",
        "--onefile-no-compression",
        "--onefile-no-dll",
        "--remove-output",
        f"--jobs={max(1, jobs)}",
        f"--output-dir={OUTPUT_DIR}",
        f"--output-filename={EXE_NAME}",
        f"--company-name={APP_CONFIG.company_name}",
        f"--product-name={APP_CONFIG.product_name}",
        f"--file-description={APP_CONFIG.file_description}",
        f"--file-version={version}",
        f"--product-version={version}",
        f"--include-data-dir={REPO_ROOT / 'Data'}=Data",
        f"--include-data-dir={SHARED_ASSETS_DIR}=Code/gui/assets",
        str(REPO_ROOT / "main.py"),
    ]

    print("Running Nuitka build ...")
    result = subprocess.run(nuitka_args, check=False, env=build_env)
    if result.returncode != 0:
        sys.exit("Nuitka build failed.")

    return OUTPUT_DIR / EXE_NAME


def find_iscc() -> Path | None:
    which = shutil.which("ISCC.exe")
    if which:
        return Path(which)

    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Inno Setup 6" / "ISCC.exe",
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def build_installer(version: str, source_exe: Path) -> Path:
    iscc = find_iscc()
    if iscc is None:
        sys.exit("ISCC.exe not found. Install Inno Setup 6 or run build.py without --installer.")
    if not INSTALLER_SCRIPT.exists():
        sys.exit(f"Installer script not found: {INSTALLER_SCRIPT}")
    if not source_exe.exists():
        sys.exit(f"Expected executable not found at {source_exe}")

    output_base = Path(INSTALLER_NAME).stem
    installer_app_id = APP_CONFIG.installer_app_id.strip().strip("{}")
    iscc_args = [
        str(iscc),
        f"/DAppName={APP_CONFIG.display_name}",
        f"/DAppVersion={version}",
        f"/DAppPublisher={APP_CONFIG.company_name}",
        f"/DAppExeName={EXE_NAME}",
        f"/DAppId={installer_app_id}",
        f"/DSourceExe={source_exe}",
        f"/DOutputDir={OUTPUT_DIR}",
        f"/DOutputBaseFilename={output_base}",
        str(INSTALLER_SCRIPT),
    ]

    print("Running Inno Setup build ...")
    result = subprocess.run(iscc_args, check=False)
    if result.returncode != 0:
        sys.exit("Inno Setup build failed.")

    installer_path = OUTPUT_DIR / INSTALLER_NAME
    if not installer_path.exists():
        sys.exit(f"Expected installer not found at {installer_path}")
    return installer_path


def resolve_release_root(override_root: str) -> Path:
    raw_root = override_root.strip() or APP_CONFIG.shared_network_root.strip()
    if not raw_root:
        sys.exit("No shared release root is configured. Set app_config.py or pass --release-root.")
    return Path(raw_root)


def ensure_release_structure(root: Path) -> None:
    for path in (root, root / "shared", root / "backups", root / "releases"):
        path.mkdir(parents=True, exist_ok=True)


def sha256_for(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def publish_release(
    version: str,
    exe_path: Path,
    installer_path: Path | None,
    release_root: Path,
    notes: str,
) -> None:
    ensure_release_structure(release_root)
    release_dir = release_root / "releases" / version
    release_dir.mkdir(parents=True, exist_ok=True)

    published_exe = release_dir / EXE_NAME
    shutil.copy2(exe_path, published_exe)

    published_installer = None
    if installer_path is not None and installer_path.exists():
        published_installer = release_dir / INSTALLER_NAME
        shutil.copy2(installer_path, published_installer)

    notes_text = notes.strip()
    if notes_text:
        (release_dir / "release_notes.txt").write_text(notes_text + "\n", encoding="utf-8")

    published_at = datetime.now().astimezone().isoformat(timespec="seconds")
    release_info = {
        "version": version,
        "published_at": published_at,
        "exe_name": EXE_NAME,
        "exe_sha256": sha256_for(published_exe),
        "installer_name": INSTALLER_NAME if published_installer else "",
        "installer_sha256": sha256_for(published_installer) if published_installer else "",
        "notes": notes_text,
    }
    (release_dir / "release.json").write_text(json.dumps(release_info, indent=2), encoding="utf-8")

    if not published_installer:
        print("Installer was not built, so current.json was not updated.")
        return

    manifest = {
        "version": version,
        "installer_path": published_installer.relative_to(release_root).as_posix(),
        "published_at": published_at,
        "notes": notes_text,
        "sha256": sha256_for(published_installer),
    }
    manifest_path = release_root / APP_CONFIG.release_manifest_filename
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Published shared release manifest: {manifest_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Build {APP_CONFIG.display_name} release artifacts")
    parser.add_argument("--recreate-venv", action="store_true", help="Wipe and recreate the build venv")
    parser.add_argument("--sign", action="store_true", help="Code-sign the generated exe and installer")
    parser.add_argument("--installer", action="store_true", help="Build the installer with Inno Setup")
    parser.add_argument(
        "--publish-shared",
        action="store_true",
        help="Copy artifacts into the configured shared release folder and update current.json",
    )
    parser.add_argument(
        "--release-root",
        default="",
        help="Override the shared release root instead of using app_config.py",
    )
    parser.add_argument(
        "--notes",
        default="",
        help="Optional release notes stored beside the published artifacts.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Number of Nuitka compile jobs to run in parallel (default: 1).",
    )
    parser.add_argument(
        "--version",
        default=DEFAULT_VERSION,
        help=f"Version string (default: {DEFAULT_VERSION})",
    )
    args = parser.parse_args()

    if args.recreate_venv and VENV_DIR.exists():
        print(f"Removing existing venv at {VENV_DIR} ...")
        shutil.rmtree(VENV_DIR)

    if args.version != APP_CONFIG.app_version:
        print(
            f"Warning: build version {args.version} does not match "
            f"app_config.py version {APP_CONFIG.app_version}."
        )

    python_exe = find_python()
    if python_exe is None:
        python_exe = create_venv()

    install_deps(python_exe)

    dist_exe = build(python_exe, args.version, args.jobs)
    if args.sign:
        sign_binary(dist_exe)

    installer_path = None
    if args.installer:
        installer_path = build_installer(args.version, dist_exe)
        if args.sign:
            sign_binary(installer_path)

    if args.publish_shared:
        publish_release(
            version=args.version,
            exe_path=dist_exe,
            installer_path=installer_path,
            release_root=resolve_release_root(args.release_root),
            notes=args.notes,
        )

    print(f"\nBuild complete: {dist_exe}")
    if installer_path is not None:
        print(f"Installer complete: {installer_path}")


if __name__ == "__main__":
    main()
