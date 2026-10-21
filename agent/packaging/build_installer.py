"""Builder script to invoke ISCC.exe on installer.iss."""

import os
import shutil
import subprocess
import sys


def build():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    iss_path = os.path.join(script_dir, "installer.iss")
    iscc_path = r"C:\cb-build\tools\innosetup\ISCC.exe"

    if not os.path.exists(iscc_path):
        print(f"ERROR: ISCC compiler not found at {iscc_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = os.path.join(script_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    print(f"Compiling {iss_path} with Inno Setup...")
    cmd = [iscc_path, f"/O{output_dir}", iss_path]
    res = subprocess.run(cmd, cwd=script_dir)
    if res.returncode != 0:
        print(f"ERROR: ISCC failed with code {res.returncode}", file=sys.stderr)
        sys.exit(res.returncode)

    setup_exe = os.path.join(output_dir, "CashbackOneAgent-Setup.exe")
    if not os.path.exists(setup_exe):
        print(f"ERROR: Expected setup exe not found: {setup_exe}", file=sys.stderr)
        sys.exit(1)

    # Place a copy in C:\cashback-stage0\ for convenient pickup by curator
    stage0_dir = r"C:\cashback-stage0"
    if os.path.exists(stage0_dir):
        stage0_setup = os.path.join(stage0_dir, "CashbackOneAgent-Setup.exe")
        shutil.copyfile(setup_exe, stage0_setup)
        print(f"Copied Setup artifact to {stage0_setup}")

    size = os.path.getsize(setup_exe)
    print(f"SUCCESS: Installer built at {setup_exe} (size: {size} bytes)")


if __name__ == "__main__":
    build()
