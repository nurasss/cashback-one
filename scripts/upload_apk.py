"""Upload release APK to hosting app/ directory via FTPS.

Usage:
    py scripts/upload_apk.py [--dry-run] [--apk PATH]
"""
import argparse
import ftplib
import hashlib
import os
import ssl
import sys
from pathlib import Path

EXPECTED_APK_SIZE = 51154339
EXPECTED_APK_SHA256 = "ddc176bc3c800d97ecacb289faa3c493ca03ca327be1996ef9fd28070a068127"
DEFAULT_APK_PATH = Path("C:/cb-out/cashback-one-1.0.1.apk")


def load_env(env_path: Path) -> dict:
    if not env_path.exists():
        raise FileNotFoundError(f"Hosting credentials file not found: {env_path}")
    env = {}
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("'\"")
    return env


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Upload signed APK to hosting app/ via FTPS")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without uploading")
    parser.add_argument("--apk", type=Path, default=DEFAULT_APK_PATH, help="Path to APK file")
    args = parser.parse_args()

    apk_path = args.apk
    if not apk_path.exists():
        print(f"ERROR: Local APK not found at {apk_path}", file=sys.stderr)
        return 1

    local_size = apk_path.stat().st_size
    print(f"Checking local APK: {apk_path}")
    print(f"  Size: {local_size} bytes (expected {EXPECTED_APK_SIZE})")
    if local_size != EXPECTED_APK_SIZE:
        print("ERROR: Local APK size mismatch!", file=sys.stderr)
        return 1

    local_hash = compute_sha256(apk_path)
    print(f"  SHA-256: {local_hash}")
    if local_hash != EXPECTED_APK_SHA256:
        print("ERROR: Local APK SHA-256 mismatch!", file=sys.stderr)
        return 1

    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env.hosting.local"
    env = load_env(env_path)

    host = env.get("HOSTING_FTPS_HOST") or env.get("FTPS_HOST")
    user = env.get("HOSTING_FTPS_USER") or env.get("FTPS_USER")
    password = env.get("HOSTING_FTPS_PASSWORD") or env.get("FTPS_PASSWORD")
    port = int(env.get("HOSTING_FTPS_PORT") or env.get("FTPS_PORT") or 21)
    site_dir = env.get("HOSTING_SITE_DIR") or env.get("FTPS_SITE_DIR")

    if not all([host, user, password, site_dir]):
        print("ERROR: Missing required FTPS settings in .env.hosting.local", file=sys.stderr)
        return 1

    target_filename = apk_path.name
    part_filename = f"{target_filename}.part"

    print(f"\nConnecting to {host}:{port} via FTPS (TLS 1.2)...")
    context = ssl.create_default_context()
    context.maximum_version = ssl.TLSVersion.TLSv1_2

    with ftplib.FTP_TLS(context=context, timeout=60) as ftp:
        ftp.connect(host, port)
        ftp.login(user, password)
        ftp.prot_p()
        ftp.cwd(site_dir)
        print(f"Connected. In site root: {ftp.pwd()}")

        # Ensure app directory exists and navigate into it
        try:
            ftp.cwd("app")
        except ftplib.error_perm:
            print("Directory 'app' not found, creating it...")
            ftp.mkd("app")
            ftp.cwd("app")

        app_dir = ftp.pwd()
        print(f"Working directory: {app_dir}")
        ftp.voidcmd("TYPE I")

        # List existing files in app/
        print("\n=== Current contents of app/ ===")
        app_listing = []
        ftp.retrlines("LIST", app_listing.append)
        for line in app_listing:
            print(f"  {line}")

        # Check if target already exists
        target_exists = False
        try:
            rem_size = ftp.size(target_filename)
            target_exists = True
            print(f"\nWARNING: {target_filename} already exists on server (size: {rem_size} bytes).")
            if rem_size == local_size:
                print("Remote file size matches local file exactly. Skipping upload to avoid overwrite.")
                return 0
            else:
                print("ERROR: Remote file exists with different size. Refusing to overwrite.", file=sys.stderr)
                return 1
        except ftplib.error_perm:
            target_exists = False

        print(f"\n=== Plan of changes ===")
        print(f"  Destination: {app_dir}/{target_filename}")
        print(f"  Step 1: Upload to temporary file '{part_filename}' ({local_size} bytes)")
        print(f"  Step 2: Verify size of '{part_filename}' on server == {local_size} bytes")
        print(f"  Step 3: Atomically rename '{part_filename}' -> '{target_filename}' (RNFR/RNTO)")
        print(f"  Step 4: Verify final '{target_filename}' size == {local_size} bytes")

        if args.dry_run:
            print("\n--dry-run enabled: no files uploaded.")
            return 0

        # Upload to part file
        print(f"\nStarting upload of {target_filename} as {part_filename}...")
        with open(apk_path, "rb") as f:
            ftp.storbinary(f"STOR {part_filename}", f, blocksize=65536)

        # Verify part file size
        part_size = ftp.size(part_filename)
        print(f"Uploaded part file size: {part_size} bytes")
        if part_size != local_size:
            print(f"ERROR: Part file size mismatch! Expected {local_size}, got {part_size}", file=sys.stderr)
            return 1

        # Rename part to target
        print(f"Renaming {part_filename} -> {target_filename}...")
        ftp.rename(part_filename, target_filename)

        # Verify final size
        final_size = ftp.size(target_filename)
        print(f"Final file size on server: {final_size} bytes")
        if final_size != local_size:
            print(f"ERROR: Final file size mismatch! Expected {local_size}, got {final_size}", file=sys.stderr)
            return 1

        print("\n=== Final contents of app/ ===")
        final_listing = []
        ftp.retrlines("LIST", final_listing.append)
        for line in final_listing:
            print(f"  {line}")

        print(f"\nUpload and verification completed successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
