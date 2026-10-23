"""Builder script to invoke ISCC.exe on installer.iss."""

import os
import re
import shutil
import subprocess
import sys


def read_agent_version(script_dir):
    init_path = os.path.join(script_dir, "..", "src", "poscenter_loyalty_agent", "__init__.py")
    with open(init_path, encoding="utf-8") as f:
        match = re.search(r'^__version__ = "([0-9]+\.[0-9]+\.[0-9]+)"$', f.read(), re.MULTILINE)
    if match is None:
        print(f"ERROR: Agent version not found in {init_path}", file=sys.stderr)
        sys.exit(1)
    return match.group(1)


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

    # Place a versioned copy in C:\cashback-stage0\agent-<version>\ for pickup by curator.
    # Never overwrite an existing Setup: older versions are kept for rollback.
    stage0_dir = r"C:\cashback-stage0"
    if os.path.exists(stage0_dir):
        version = read_agent_version(script_dir)
        stage0_setup = os.path.join(stage0_dir, f"agent-{version}", f"CashbackOneAgent-Setup-{version}.exe")
        if os.path.exists(stage0_setup):
            print(f"Kept existing {stage0_setup}; not overwritten")
        else:
            os.makedirs(os.path.dirname(stage0_setup), exist_ok=True)
            shutil.copyfile(setup_exe, stage0_setup)
            print(f"Copied Setup artifact to {stage0_setup}")

    size = os.path.getsize(setup_exe)
    print(f"SUCCESS: Installer built at {setup_exe} (size: {size} bytes)")


if __name__ == "__main__":
    build()
