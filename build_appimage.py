#!/usr/bin/env python3
"""Build an AppImage for Mark Editor 4.

Requirements:
    - Python 3 with venv module
    - GTK4 runtime libraries on the host
    - appimagetool (download from https://github.com/AppImage/AppImageKit/releases)

Usage:
    python3 build_appimage.py
"""

import os
import shutil
import subprocess
import sys

APP_ID = "com.github.mark_editor"
APP_NAME = "Mark Editor"
VERSION = "0.6.2"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_DIR = os.path.join(BASE_DIR, "mark_editor")
ICON_SRC = os.path.join(BASE_DIR, "images", "mark_editor.png")
DESKTOP_SRC = os.path.join(BASE_DIR, "mark-editor.desktop")
BUILD_DIR = os.path.join(BASE_DIR, "AppDir")
OUTPUT = os.path.join(BASE_DIR, f"MarkEditor-{VERSION}-x86_64.AppImage")


def run(cmd: list[str], **kwargs) -> None:
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=BASE_DIR, **kwargs)


def step(msg: str) -> None:
    print(f"\n==> {msg}")


def clean() -> None:
    step("Cleaning old builds")
    for p in (BUILD_DIR, OUTPUT):
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.isfile(p):
            os.remove(p)


def create_appdir() -> None:
    step("Creating AppDir structure")

    # Directories
    for d in [
        os.path.join(BUILD_DIR, "usr", "bin"),
        os.path.join(BUILD_DIR, "usr", "share", "mark_editor"),
        os.path.join(BUILD_DIR, "usr", "share", "icons", "hicolor", "256x256", "apps"),
    ]:
        os.makedirs(d, exist_ok=True)

    # Copy package files
    for f in os.listdir(PACKAGE_DIR):
        if f.endswith(".py") or f.endswith(".css"):
            shutil.copy2(os.path.join(PACKAGE_DIR, f),
                        os.path.join(BUILD_DIR, "usr", "share", "mark_editor", f))

    # Copy requirements
    shutil.copy2(os.path.join(BASE_DIR, "requirements.txt"),
                os.path.join(BUILD_DIR, "usr", "share", "requirements.txt"))

    # Create wrapper script
    wrapper = os.path.join(BUILD_DIR, "usr", "bin", "mark-editor")
    with open(wrapper, "w") as f:
        f.write("#!/bin/bash\n")
        f.write('DIR="$(dirname "$(readlink -f "$0")")"\n')
        f.write('SHARE_DIR="$(dirname "$DIR")/share"\n')
        f.write('export PYTHONPATH="$SHARE_DIR:$PYTHONPATH"\n')
        f.write('cd "$SHARE_DIR"\n')
        f.write('exec python3 -m mark_editor.main "$@"\n')
    os.chmod(wrapper, 0o755)

    # Icon
    shutil.copy2(ICON_SRC, os.path.join(BUILD_DIR, "usr", "share", "icons", "hicolor", "256x256", "apps", "mark-editor.png"))
    shutil.copy2(ICON_SRC, os.path.join(BUILD_DIR, "mark-editor.png"))

    # Desktop file
    with open(DESKTOP_SRC) as f:
        desktop = f.read()
    desktop = desktop.replace("Icon=images/mark_editor.png", "Icon=mark-editor")
    with open(os.path.join(BUILD_DIR, "mark-editor.desktop"), "w") as f:
        f.write(desktop)

    # AppRun — the entry point the AppImage runtime executes
    apprun = os.path.join(BUILD_DIR, "AppRun")
    os.symlink("usr/bin/mark-editor", apprun)

    print(f"  AppDir created at {BUILD_DIR}")


def build_appimage() -> None:
    step("Building AppImage")
    # Find appimagetool
    tool = shutil.which("appimagetool")
    if not tool:
        tool = os.path.join(BASE_DIR, "appimagetool")
    if not os.path.isfile(tool):
        print("ERROR: appimagetool not found.")
        print("  Download from: https://github.com/AppImage/AppImageKit/releases")
        print("  Or place it in the project directory as 'appimagetool'")
        sys.exit(1)

    env = os.environ.copy()
    env["ARCH"] = "x86_64"
    run([tool, "--no-appstream", BUILD_DIR, OUTPUT], env=env)
    size_mb = os.path.getsize(OUTPUT) / (1024 * 1024)
    print(f"\n  Built: {OUTPUT}")
    print(f"  Size:  {size_mb:.1f} MB")


def main() -> None:
    print(f"Building {APP_NAME} AppImage v{VERSION}")
    clean()
    create_appdir()
    build_appimage()


if __name__ == "__main__":
    main()
