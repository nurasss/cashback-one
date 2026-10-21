"""Build script for PyInstaller onedir CashbackOneAgent."""

import os
import subprocess
import sys


def build():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(script_dir, "dist")
    work_dir = os.path.join(script_dir, "build")
    spec_file = os.path.join(script_dir, "CashbackOneAgent.spec")

    print(f"Building CashbackOneAgent in {script_dir}...")
    print(f"Using Python: {sys.executable}")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        f"--distpath={dist_dir}",
        f"--workpath={work_dir}",
        spec_file,
    ]

    res = subprocess.run(cmd, cwd=script_dir)
    if res.returncode != 0:
        print(f"ERROR: PyInstaller failed with code {res.returncode}", file=sys.stderr)
        sys.exit(res.returncode)

    exe_path = os.path.join(dist_dir, "CashbackOneAgent", "CashbackOneAgent.exe")
    if not os.path.exists(exe_path):
        print(f"ERROR: Expected binary not found: {exe_path}", file=sys.stderr)
        sys.exit(1)

    print(f"SUCCESS: Binary built at {exe_path}")

if __name__ == "__main__":
    build()
