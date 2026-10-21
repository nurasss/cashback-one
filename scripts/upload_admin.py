"""Upload admin SPA (admin/dist/) to hosting site directory via FTPS.

Usage:
    python scripts/upload_admin.py [--dry-run]
"""
import argparse
import ftplib
import hashlib
import os
import ssl
import sys
from pathlib import Path


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


def ensure_remote_dir(ftp: ftplib.FTP_TLS, remote_dir: str):
    parts = remote_dir.strip("/").split("/")
    current = ""
    for part in parts:
        current = f"{current}/{part}" if current else part
        try:
            ftp.cwd(part)
        except ftplib.error_perm:
            try:
                ftp.mkd(part)
                ftp.cwd(part)
            except ftplib.error_perm:
                pass


def main():
    parser = argparse.ArgumentParser(description="Upload admin dist to hosting via FTPS")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without uploading")
    parser.add_argument("--with-htaccess", action="store_true", help="Also upload default SPA .htaccess if missing")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    dist_dir = repo_root / "admin" / "dist"
    if not dist_dir.exists():
        print(f"ERROR: {dist_dir} does not exist. Run npm run build first.", file=sys.stderr)
        return 1

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

    local_files = []
    for root, _, files in os.walk(dist_dir):
        for f in files:
            full_path = Path(root) / f
            rel_path = full_path.relative_to(dist_dir).as_posix()
            local_files.append((rel_path, full_path, full_path.stat().st_size))

    print(f"Connecting to {host}:{port} via FTPS (TLS 1.2)...")
    context = ssl.create_default_context()
    context.maximum_version = ssl.TLSVersion.TLSv1_2

    with ftplib.FTP_TLS(context=context, timeout=30) as ftp:
        ftp.connect(host, port)
        ftp.login(user, password)
        ftp.prot_p()
        ftp.cwd(site_dir)
        admin_root = ftp.pwd()
        ftp.voidcmd("TYPE I")

        actions = []

        # Check existing remote files
        for rel_path, local_path, local_size in local_files:
            remote_parts = rel_path.split("/")
            remote_filename = remote_parts[-1]
            remote_subdir = "/".join(remote_parts[:-1])

            # Navigate to subdirectory if needed
            if remote_subdir:
                try:
                    ftp.cwd(f"{admin_root}/{remote_subdir}")
                except ftplib.error_perm:
                    actions.append(("CREATE_DIR_AND_UPLOAD", rel_path, local_size, 0))
                    ftp.cwd(admin_root)
                    continue
            else:
                ftp.cwd(admin_root)

            try:
                remote_size = ftp.size(remote_filename)
                if remote_size == local_size:
                    # Same size, check if it's hashed asset
                    if "assets/" in rel_path:
                        actions.append(("SKIP_IDENTICAL", rel_path, local_size, remote_size))
                    else:
                        actions.append(("UPDATE", rel_path, local_size, remote_size))
                else:
                    actions.append(("UPDATE", rel_path, local_size, remote_size))
            except ftplib.error_perm:
                actions.append(("UPLOAD_NEW", rel_path, local_size, 0))

        # Check .htaccess
        ftp.cwd(admin_root)
        has_htaccess = False
        try:
            ht_size = ftp.size(".htaccess")
            has_htaccess = True
            print(f"Remote .htaccess found on server (size: {ht_size} bytes). Preserving untouched.")
        except ftplib.error_perm:
            print("Remote .htaccess NOT found on server.")

        print("\n=== Plan of changes ===")
        for action, path_str, l_sz, r_sz in actions:
            if action == "SKIP_IDENTICAL":
                print(f"  [SKIP]   {path_str} (size {l_sz} matches remote)")
            elif action == "UPLOAD_NEW":
                print(f"  [CREATE] {path_str} ({l_sz} bytes)")
            elif action == "CREATE_DIR_AND_UPLOAD":
                print(f"  [MKDIR+UPLOAD] {path_str} ({l_sz} bytes)")
            elif action == "UPDATE":
                print(f"  [UPDATE] {path_str} ({r_sz} -> {l_sz} bytes)")

        if args.dry_run:
            print("\n--dry-run enabled: no files modified.")
            return 0

        print("\nStarting upload...")
        for action, path_str, l_sz, r_sz in actions:
            if action == "SKIP_IDENTICAL":
                continue
            local_path = dist_dir / path_str
            remote_parts = path_str.split("/")
            remote_filename = remote_parts[-1]
            remote_subdir = "/".join(remote_parts[:-1])

            ftp.cwd(admin_root)
            if remote_subdir:
                ensure_remote_dir(ftp, remote_subdir)

            print(f"Uploading {path_str} ({l_sz} bytes)...", end="", flush=True)
            with open(local_path, "rb") as f:
                ftp.storbinary(f"STOR {remote_filename}", f)

            # Verify size
            uploaded_size = ftp.size(remote_filename)
            if uploaded_size != l_sz:
                print(f" FAILED (size mismatch: local {l_sz} != remote {uploaded_size})")
                return 1
            print(" OK")

        print("\nUpload completed successfully and verified.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
