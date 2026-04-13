"""Nuitka build script for a reusable inventory app variant.

Usage:
    python build.py
    python build.py --recreate-venv
    python build.py --sign
    python build.py --version 1.2.0
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app_config import APP_CONFIG

REPO_ROOT = Path(__file__).resolve().parent
SHARED_ROOT = REPO_ROOT.parent / "shared_core"
SHARED_ASSETS_DIR = SHARED_ROOT / "Code" / "gui" / "assets"
VENV_DIR = REPO_ROOT / ".venv312"
OUTPUT_DIR = REPO_ROOT / "Output"
EXE_NAME = APP_CONFIG.build_exe_name
PYTHON_VERSION = "3.12"
DEFAULT_VERSION = "1.0.0"


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


def sign_exe(exe_path: Path) -> None:
    signtool = find_signtool()
    if not signtool:
        sys.exit("signtool.exe not found. Install the Windows SDK or remove --sign.")

    if not exe_path.exists():
        sys.exit(f"Expected executable not found at {exe_path}")

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
            str(exe_path),
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
            str(exe_path),
        ]
    else:
        sys.exit(
            "Set CODE_SIGN_PFX_PATH/CODE_SIGN_PFX_PASSWORD or CODE_SIGN_SUBJECT_NAME "
            "before using --sign."
        )

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        sys.exit("Code signing failed.")


def build(python_exe: Path, version: str) -> Path:
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


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Build {APP_CONFIG.display_name} .exe with Nuitka")
    parser.add_argument("--recreate-venv", action="store_true", help="Wipe and recreate the build venv")
    parser.add_argument("--sign", action="store_true", help="Code-sign the output exe")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="Version string (default: 1.0.0)")
    args = parser.parse_args()

    if args.recreate_venv and VENV_DIR.exists():
        print(f"Removing existing venv at {VENV_DIR} ...")
        shutil.rmtree(VENV_DIR)

    python_exe = find_python()
    if python_exe is None:
        python_exe = create_venv()

    install_deps(python_exe)

    dist_exe = build(python_exe, args.version)

    if args.sign:
        sign_exe(dist_exe)

    print(f"\nBuild complete: {dist_exe}")


if __name__ == "__main__":
    main()
