#!/usr/bin/env python
"""Build (and by default install) the Quantly C++ engine wheel reproducibly.

On Linux/macOS the stock toolchain is used and no special setup is needed. On
Windows without MSVC we fall back to the MSYS2 **ucrt64** GCC + Ninja; the
runtime is statically linked (see CMakeLists.txt) so the resulting .pyd loads
under a stock, MSVC-built CPython.

Usage:
    python engine/scripts/build_wheel.py            # build + install
    python engine/scripts/build_wheel.py --no-install
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
DIST = ENGINE_DIR / "dist"
UCRT64 = Path(r"C:\msys64\ucrt64\bin")


def _toolchain_env() -> dict:
    env = os.environ.copy()
    if not sys.platform.startswith("win"):
        return env
    # a real MSVC or a caller-provided compiler wins
    if shutil.which("cl") or env.get("CXX"):
        return env
    gpp = UCRT64 / "g++.exe"
    if not gpp.exists():
        raise SystemExit(
            "no MSVC and no MSYS2 ucrt64 g++ found; install one to build the engine"
        )
    env["CC"] = str(UCRT64 / "gcc.exe")
    env["CXX"] = str(gpp)
    env["CMAKE_GENERATOR"] = "Ninja"
    ninja = Path(sys.executable).parent / "ninja.exe"
    if ninja.exists():
        env["CMAKE_MAKE_PROGRAM"] = str(ninja)
    return env


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-install", action="store_true", help="build the wheel only"
    )
    args = parser.parse_args()

    env = _toolchain_env()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            str(ENGINE_DIR),
            "--no-build-isolation",
            "-w",
            str(DIST),
        ],
        check=True,
        env=env,
    )

    if args.no_install:
        return
    wheels = sorted(glob.glob(str(DIST / "quantly_engine-*.whl")), key=os.path.getmtime)
    if not wheels:
        raise SystemExit("no wheel produced")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            "--no-deps",
            wheels[-1],
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
