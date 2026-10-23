"""Verification script for CashbackOneAgent and CashbackOneAgent-Setup.exe (read-only inspection)."""

import hashlib
import os
import subprocess
import sys

import pefile


def get_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def verify() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(script_dir, "dist", "CashbackOneAgent")
    exe_path = os.path.join(dist_dir, "CashbackOneAgent.exe")
    setup_path = os.path.join(script_dir, "output", "CashbackOneAgent-Setup.exe")

    print("=== Verification of Build Artifacts (Read-Only) ===")

    # 1. Existence and Hashes
    assert os.path.exists(exe_path), f"Missing {exe_path}"
    assert os.path.exists(setup_path), f"Missing {setup_path}"

    exe_size = os.path.getsize(exe_path)
    exe_hash = get_sha256(exe_path)
    setup_size = os.path.getsize(setup_path)
    setup_hash = get_sha256(setup_path)

    print(f"Agent Binary:   {exe_path}")
    print(f"  Size:         {exe_size} bytes ({exe_size / (1024*1024):.2f} MB)")
    print(f"  SHA-256:      {exe_hash}")
    print(f"Setup Package:  {setup_path}")
    print(f"  Size:         {setup_size} bytes ({setup_size / (1024*1024):.2f} MB)")
    print(f"  SHA-256:      {setup_hash}")

    # 2. PE Architecture
    pe_exe = pefile.PE(exe_path)
    pe_setup = pefile.PE(setup_path)
    # 0x014c is IMAGE_FILE_MACHINE_I386
    assert pe_exe.FILE_HEADER.Machine == 0x014c, "Agent EXE is not 32-bit x86!"
    assert pe_setup.FILE_HEADER.Machine == 0x014c, "Setup EXE is not 32-bit x86!"
    print("Architecture Check: Both binaries are 32-bit x86 (IMAGE_FILE_MACHINE_I386: 0x014c).")

    # 3. CLI --help and --version checks
    isolated_env = {"SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows")}
    r_ver = subprocess.run([exe_path, "--version"], env=isolated_env, capture_output=True, text=True)
    assert r_ver.returncode == 0, f"--version failed with code {r_ver.returncode}"
    assert "0.2.2" in r_ver.stdout, f"--version output unexpected: {r_ver.stdout}"
    print(f"Safe --version: Exit code {r_ver.returncode}, Output: {r_ver.stdout.strip()}")

    r_help = subprocess.run([exe_path, "--help"], env=isolated_env, capture_output=True, text=True)
    assert r_help.returncode == 0, f"--help failed with code {r_help.returncode}"
    assert "usage:" in r_help.stdout, f"--help output unexpected: {r_help.stdout}"
    print(f"Safe --help:    Exit code {r_help.returncode}, Usage displayed properly.")

    # 4. Completeness of Bundled Components
    internal_dir = os.path.join(dist_dir, "_internal")
    assert os.path.exists(os.path.join(internal_dir, "python311.dll")), "Missing python311.dll"
    assert os.path.exists(os.path.join(internal_dir, "pywin32_system32", "pythoncom311.dll")), "Missing pythoncom311.dll"
    assert os.path.exists(os.path.join(internal_dir, "pywin32_system32", "pywintypes311.dll")), "Missing pywintypes311.dll"
    assert os.path.exists(os.path.join(internal_dir, "win32", "servicemanager.pyd")), "Missing servicemanager.pyd"
    assert os.path.exists(os.path.join(internal_dir, "certifi", "cacert.pem")), "Missing certifi cacert.pem"
    assert os.path.exists(os.path.join(internal_dir, "tzdata", "zoneinfo", "Asia", "Almaty")), "Missing tzdata Asia/Almaty"
    print("Completeness Check: python311.dll, pywin32 (pythoncom, pywintypes, servicemanager), certifi, tzdata present.")

    # 5. File Inventory Audit for Sensitive / Transient Data
    forbidden_terms = [".env", ".key", "stage0_mapping", ".db", "stage0_output", "prod_run.log", "id_rsa"]
    leaks = []
    for root, _dirs, files in os.walk(dist_dir):
        for f in files:
            lower = f.lower()
            for term in forbidden_terms:
                if term in lower:
                    if not lower.endswith(".pyc") and not lower.endswith(".pyd"):
                        leaks.append(os.path.join(root, f))

    if leaks:
        print(f"ERROR: Forbidden files found in distribution: {leaks}", file=sys.stderr)
        sys.exit(1)
    print("File Inventory Audit: PASSED. Zero sensitive files (.env, .key, stage0 data, logs) bundled.")

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    verify()
