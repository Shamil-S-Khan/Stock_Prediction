"""
Pack the finance_forecasting project into a ZIP file, excluding ANY virtual environments.
- Keeps: data/, models/, source, templates, static, docs, REPORT.md, requirements.txt
- Excludes: tf-env, venv, .venv, env, ENV, __pycache__, .pytest_cache, .git and any folder detected as a venv

Usage (Windows PowerShell):
  python .\zip_project.py                       # writes to Desktop\finance_forecasting_submission.zip
  python .\zip_project.py --out C:\path\out.zip # custom output path
  python .\zip_project.py --root C:\path\finance_forecasting # custom project root
"""
from __future__ import annotations

import argparse
import os
import sys
import zipfile
from pathlib import Path
from datetime import datetime

# Default settings
DEFAULT_ROOT = Path(__file__).resolve().parent  # finance_forecasting directory
DEFAULT_OUT = Path.home() / "Desktop" / "finance_forecasting_submission.zip"

# Directory names to always exclude (case-insensitive)
ALWAYS_EXCLUDE_DIRS = {
    "tf-env", "tf_env", "venv", ".venv", "env", "ENV",
    "__pycache__", ".pytest_cache", ".git", ".idea", ".vscode",
}

# File extensions to exclude (keep project small and clean)
EXCLUDE_FILE_EXT = {
    ".pyc", ".pyo",
}

# Common venv subfolders to exclude if present directly under project root
COMMON_VENV_SUBDIRS = {"Lib", "Scripts", "Include", "bin", "lib", "include"}


def is_venv_dir(path: Path) -> bool:
    """Heuristically detect a Python virtual environment directory."""
    try:
        if not path.is_dir():
            return False
        # Explicit marker
        if (path / "pyvenv.cfg").exists():
            return True
        # Typical Windows venv structure
        if (path / "Scripts" / "Activate.ps1").exists():
            return True
        # Typical POSIX venv structure
        if (path / "bin" / "activate").exists():
            return True
    except Exception:
        return False
    return False


def should_exclude_dir(rel_dir: Path, abs_dir: Path) -> bool:
    # Exclude by name
    name = rel_dir.name
    if name.lower() in {d.lower() for d in ALWAYS_EXCLUDE_DIRS}:
        return True
    # Dynamic venv detection
    if is_venv_dir(abs_dir):
        return True
    # If project root mistakenly contains venv subfolders, exclude them too
    if name in COMMON_VENV_SUBDIRS:
        # Only exclude if we also see pyvenv.cfg at project root to avoid false positives
        proj_root = DEFAULT_ROOT
        if (proj_root / "pyvenv.cfg").exists():
            return True
    return False


def should_exclude_file(rel_file: Path) -> bool:
    if rel_file.suffix.lower() in EXCLUDE_FILE_EXT:
        return True
    return False


def zip_directory(project_root: Path, out_zip: Path) -> None:
    project_root = project_root.resolve()
    out_zip = out_zip.resolve()

    out_zip.parent.mkdir(parents=True, exist_ok=True)

    # Use a temp file first to avoid partial zips if interrupted
    tmp_zip = out_zip.with_suffix(".partial.zip")
    if tmp_zip.exists():
        tmp_zip.unlink()

    entries = 0
    skipped_dirs = []

    with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(project_root):
            abs_root = Path(root)
            rel_root = abs_root.relative_to(project_root)

            # Prune directories in-place
            kept_dirs = []
            for d in dirs:
                rel_d = rel_root / d
                abs_d = abs_root / d
                if should_exclude_dir(rel_d, abs_d):
                    skipped_dirs.append(str(rel_d))
                    continue
                kept_dirs.append(d)
            dirs[:] = kept_dirs

            # Add files
            for f in files:
                rel_f = rel_root / f
                if should_exclude_file(rel_f):
                    continue
                abs_f = abs_root / f
                # Ensure within root
                try:
                    abs_f.relative_to(project_root)
                except Exception:
                    continue
                z.write(abs_f, arcname=str(rel_f))
                entries += 1

    # Move temp to final
    if out_zip.exists():
        out_zip.unlink()
    tmp_zip.rename(out_zip)

    print(f"\nZIP created: {out_zip}")
    print(f"Included files: {entries}")
    if skipped_dirs:
        unique_skipped = sorted(set(skipped_dirs))
        print("Excluded directories (sample):")
        for d in unique_skipped[:10]:
            print(f"  - {d}")
        if len(unique_skipped) > 10:
            print(f"  ... and {len(unique_skipped) - 10} more")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Zip the project excluding any virtual environments.")
    p.add_argument("--root", type=str, default=str(DEFAULT_ROOT), help="Project root (defaults to this script's folder)")
    p.add_argument("--out", type=str, default=str(DEFAULT_OUT), help="Output zip path (defaults to Desktop)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    project_root = Path(args.root).resolve()
    out_zip = Path(args.out).resolve()

    if not project_root.exists():
        print(f"Error: root does not exist: {project_root}")
        sys.exit(1)

    print("Packaging project with settings:")
    print(f"  Root: {project_root}")
    print(f"  Out:  {out_zip}")

    start = datetime.now()
    zip_directory(project_root, out_zip)
    elapsed = datetime.now() - start
    print(f"Done in {elapsed.total_seconds():.2f}s")


if __name__ == "__main__":
    main()
