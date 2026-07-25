#!/usr/bin/env python3
import os
import sys
import time
import argparse
import hashlib
import ftplib
import socket
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import json

# --- CONFIGURATION DEFAULTS ---
DEFAULT_CONFIG = {
    "scan_ip_start": "10.0.0.100",
    "scan_ip_end": "10.0.0.129",
    "ftp_port": 5000,
    "timeout": 3,
    "mappings": [
        ["/run/media/SN01T/emudeck/Emulation/roms/gb", "/ROMs/gb"],
        ["/run/media/SN01T/emudeck/Emulation/roms/nes", "/ROMs/nes"]
    ],
    "aliases": {
        "Pokemon_Emerald_Patched.gba": "Pokemon - Emerald Version (USA).gba",
        "Pokemon_Emerald_Patched.sav": "Pokemon - Emerald Version (USA).sav"
    },
    "valid_extensions": [".gba", ".nds", ".sav", ".gb", ".gbc", ".cia"],
    "confirm_on_conflict": True,
    "bulk_override_policy": "prompt"  # prompt | source_wins | destination_wins
}

# Paths for configuration and state
CONFIG_DIR = os.path.expanduser("~/.config/deck-console-mgr")
DEFAULT_CONFIG_PATH = os.path.join(CONFIG_DIR, "default.json")
DEVICES_DIR = os.path.join(CONFIG_DIR, "devices")
DB_PATH = os.path.join(CONFIG_DIR, "3ds_sync_db.json")
BACKUP_DIR = os.path.join(CONFIG_DIR, "backups")
CLOUD_SAVE_DIR = os.path.join(CONFIG_DIR, "cloud_saves")

os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(DEVICES_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(CLOUD_SAVE_DIR, exist_ok=True)


# --- UTILITY: Config & State ---
def load_default_config():
    cfg = DEFAULT_CONFIG.copy()
    try:
        if os.path.exists(DEFAULT_CONFIG_PATH):
            with open(DEFAULT_CONFIG_PATH, 'r') as f:
                on_disk = json.load(f)
                cfg.update(on_disk)
    except Exception:
        pass
    return cfg


def device_config_path(mac):
    safe = mac.replace(':', '').lower()
    return os.path.join(DEVICES_DIR, f"{safe}.json")


def load_device_config(mac):
    path = device_config_path(mac)
    cfg = {}
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    return cfg


def save_device_config(mac, cfg):
    path = device_config_path(mac)
    with open(path, 'w') as f:
        json.dump(cfg, f, indent=2)


class StateDatabase:
    def __init__(self, path=DB_PATH):
        self.db_path = path
        self.data = {}
        self.load()

    def load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}

    def save(self):
        try:
            with open(self.db_path, 'w') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"❌ Error writing database: {e}")

    def get_by_sha(self, sha):
        return self.data.get(sha)

    def update_entry(self, sha, local_file, remote_file):
        self.data[sha] = {
            "local_path": local_file,
            "remote_path": remote_file,
            "updated_at": datetime.now().isoformat()
        }
        self.save()


# --- NETWORK DISCOVERY ---
def scan_single_ip(ip, port, timeout):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return ip
    except (socket.timeout, ConnectionRefusedError, OSError):
        return None


def locate_active_ips(start_ip, end_ip, port, timeout):
    base_ip = ".".join(start_ip.split(".")[:3])
    start_suffix = int(start_ip.split(".")[3])
    end_suffix = int(end_ip.split(".")[3])
    ips_to_scan = [f"{base_ip}.{i}" for i in range(start_suffix, end_suffix + 1)]
    active_ips = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        results = executor.map(lambda ip: scan_single_ip(ip, port, timeout), ips_to_scan)
        for res in results:
            if res:
                active_ips.append(res)
    return active_ips


def get_mac_from_proc_arp(target_ip):
    if not os.path.exists("/proc/net/arp"):
        return None
    try:
        with open("/proc/net/arp", "r") as f:
            lines = f.readlines()[1:]
            for line in lines:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == target_ip:
                    mac = parts[3]
                    if mac != "00:00:00:00:00:00":
                        return mac.lower()
    except Exception:
        pass
    return None


def resolve_device_ip(cfg):
    print("🌐 Scanning network range for console device...")
    active_ips = locate_active_ips(cfg['scan_ip_start'], cfg['scan_ip_end'], cfg['ftp_port'], cfg['timeout'])
    if not active_ips:
        print("❌ ERROR: No active FTP endpoints found within specified range.")
        sys.exit(1)
    for ip in active_ips:
        mac = get_mac_from_proc_arp(ip)
        if mac:
            # load device config, prompt for human name if needed
            devcfg = load_device_config(mac)
            if 'human_name' not in devcfg:
                print(f"Discovered new device at {ip} with MAC {mac}")
                try:
                    sys.stdout.write("Please enter a human-friendly name for this device (leave blank to use MAC): ")
                    sys.stdout.flush()
                    name = sys.stdin.readline().strip()
                except KeyboardInterrupt:
                    print("\nAborted.")
                    sys.exit(0)
                if not name:
                    name = f"Console-{mac[-5:].replace(':', '')}"
                devcfg['human_name'] = name
                devcfg['first_seen'] = datetime.now().isoformat()
                devcfg['last_known_ip'] = ip
                devcfg.setdefault('cloud_share', False)
                devcfg.setdefault('conflict_policy', 'prompt')
                save_device_config(mac, devcfg)
            else:
                devcfg['last_known_ip'] = ip
                save_device_config(mac, devcfg)
            print(f"✅ Target Located: {devcfg['human_name']} ({mac}) at IP {ip}")
            return ip, mac
    print(f"⚠️  Could not confirm MAC mapping. Defaulting to first responsive target: {active_ips[0]}")
    return active_ips[0], None


# --- CRYPTO & UTILITIES ---
def calculate_sha256(filepath):
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None


def parse_mlsd_date(modify_str):
    if not modify_str:
        return 0
    try:
        fmt = "%Y%m%d%H%M%S"
        base_str = modify_str.split('.')[0]
        dt = datetime.strptime(base_str[:14], fmt)
        return int(dt.timestamp())
    except Exception:
        return 0


def create_save_backup(local_path):
    if not os.path.exists(local_path):
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = os.path.join(BACKUP_DIR, timestamp)
    os.makedirs(session_dir, exist_ok=True)
    dest = os.path.join(session_dir, os.path.basename(local_path))
    try:
        with open(local_path, 'rb') as src_f, open(dest, 'wb') as dst_f:
            dst_f.write(src_f.read())
    except Exception as e:
        print(f"⚠️  Backup execution warning: {e}")


# --- FTP Helpers ---
def ensure_remote_dir(ftp, remote_dir):
    # Create nested directories on the FTP server, relative to root if remote_dir starts with '/'
    parts = [p for p in remote_dir.strip('/').split('/') if p]
    if not parts:
        return
    # Try to change to root first if server supports absolute paths
    try:
        ftp.cwd('/')
    except Exception:
        pass
    for part in parts:
        try:
            ftp.cwd(part)
        except Exception:
            try:
                ftp.mkd(part)
                ftp.cwd(part)
            except Exception:
                # If we cannot create or cd, try to continue but operations may fail
                pass
    # After creation, leave cwd where it is; caller will cwd to desired dir explicitly


def ftp_cwd_safe(ftp, remote_dir):
    # Try absolute then relative
    try:
        ftp.cwd(remote_dir)
        return True
    except Exception:
        # Try building path piece by piece
        try:
            ensure_remote_dir(ftp, remote_dir)
            ftp.cwd(remote_dir)
            return True
        except Exception:
            return False


def upload_to_device(ip, port, remote_parent_dir, filename, local_file_path, timeout=3):
    try:
        conn = ftplib.FTP()
        conn.connect(ip, port, timeout=timeout)
        conn.login()
        ensure_remote_dir(conn, remote_parent_dir)
        conn.cwd(remote_parent_dir)
        with open(local_file_path, 'rb') as f:
            conn.storbinary(f"STOR {filename}", f)
        try:
            conn.quit()
        except Exception:
            conn.close()
        return True
    except Exception as e:
        print(f"⚠️  Failed to upload to device {ip}: {e}")
        return False


# --- INTERACTIVE HELPERS ---
def confirm_action(prompt_text, ask_confirm, dry_run):
    if dry_run:
        print(f"🔍 [DRY-RUN] Would perform: {prompt_text}")
        return False
    if not ask_confirm:
        print(f"🚀 Executing: {prompt_text}")
        return True
    try:
        sys.stdout.write(f"   👉 {prompt_text} - Proceed? (y/N): ")
        sys.stdout.flush()
        choice = sys.stdin.readline().strip().lower()
        if choice in ('y', 'yes'):
            return True
    except KeyboardInterrupt:
        print("\n Aborted.")
        sys.exit(0)
    print("   Skip modification layout loop.")
    return False


# --- CLOUD SAVE HELPERS ---
def archive_save(local_path, remote_rel_path):
    # Mirror save into cloud archive under CLOUD_SAVE_DIR preserving relative paths
    dest = os.path.join(CLOUD_SAVE_DIR, remote_rel_path.lstrip('/'))
    dest_dir = os.path.dirname(dest)
    os.makedirs(dest_dir, exist_ok=True)
    try:
        with open(local_path, 'rb') as src, open(dest, 'wb') as dst:
            dst.write(src.read())
        return dest
    except Exception as e:
        print(f"⚠️  Failed to archive save: {e}")
        return None


def propagate_save_to_cloud_devices(cfg, db, this_mac, remote_rel_path, local_save_path, dry_run):
    # Iterate devices in DEVICES_DIR, find those with cloud_share=true and upload archived save
    for fname in os.listdir(DEVICES_DIR):
        if not fname.endswith('.json'):
            continue
        mac = ':'.join([fname[i:i+2] for i in range(0, len(fname)-4, 2)])
        if mac.replace(':', '').lower() == (this_mac or '').replace(':', '').lower():
            continue
        path = os.path.join(DEVICES_DIR, fname)
        try:
            with open(path, 'r') as f:
                dev = json.load(f)
        except Exception:
            continue
        if not dev.get('cloud_share'):
            continue
        ip = dev.get('last_known_ip')
        if not ip:
            continue
        remote_parent = os.path.dirname(remote_rel_path)
        if dry_run:
            print(f"🔍 [DRY-RUN] Would propagate save to {dev.get('human_name', mac)} at {ip}: {remote_rel_path}")
            continue
        print(f"🔁 Propagating save to {dev.get('human_name', mac)} at {ip}: {remote_rel_path}")
        upload_to_device(ip, cfg.get('ftp_port'), remote_parent, os.path.basename(remote_rel_path), local_save_path, timeout=cfg.get('timeout'))


# --- MAIN ENGINE ---
def main():
    parser = argparse.ArgumentParser(description="Steam Deck Console Data Synchronizer")
    parser.add_argument('--apply', action='store_false', dest='dry_run', default=True, help="Enables live modification writes.")
    parser.add_argument('--pull-saves', action='store_true', help="Enables bidirectional sync for .sav assets.")
    parser.add_argument('--clean-remote', action='store_true', help="Removes orphaned files from the target console.")
    parser.add_argument('--confirm', action='store_true', help="Prompts user confirmation before individual operations.")
    parser.add_argument('--verbose', action='store_true', help="Outputs detailed matched and skipped items.")
    parser.add_argument('--device', help="Operate on a specific device MAC (no colons).")
    parser.add_argument('--cloud-sync', action='store_true', help="Propagate archived saves to other devices that opted into cloud_share.")
    args = parser.parse_args()

    cfg = load_default_config()

    print("==================================================")
    print("🔍 DRY-RUN MODE ACTIVE" if args.dry_run else "🚀 LIVE APPLICATION MODE ACTIVE")
    if args.pull_saves: print("📥 Bidirectional Save Sync Enabled (mtime preference)")
    if args.clean_remote: print("🗑  Remote Target Cleanup Sweeps Enabled")
    if args.confirm: print("✋ Interactive Confirmations Active")
    if args.cloud_sync: print("☁️  Cloud-save propagation enabled")
    print("==================================================")

    target_ip, mac = resolve_device_ip(cfg)
    if args.device:
        # device arg given as hexstring maybe without colons
        mac = args.device
    db = StateDatabase()

    print("Connecting to console FTP file systems...")
    try:
        ftp = ftplib.FTP()
        ftp.connect(target_ip, cfg['ftp_port'], timeout=cfg['timeout'])
        ftp.login()
    except Exception as e:
        print(f"❌ FTP Connection Failed: {e}")
        sys.exit(1)

    all_local_basenames = set()
    protected_remote_paths = set()

    # Convert valid extensions to tuple and lower-case
    VALID_EXTENSIONS = tuple([e.lower() for e in cfg.get('valid_extensions', [])])
    ALIASES = cfg.get('aliases', {})

    for local_dir, remote_dir in cfg.get('mappings', []):
        if not os.path.isdir(local_dir):
            if args.verbose:
                print(f"Local mapping not present, skipping: {local_dir}")
            continue
        if args.verbose:
            print(f"Checking directory: {local_dir} -> {remote_dir}")

        # Build remote file listing; try to cwd into remote_dir first
        remote_files = {}
        tried_cwd = ftp_cwd_safe(ftp, remote_dir)
        if tried_cwd:
            try:
                for name, facts in ftp.mlsd():
                    if facts.get('type') == 'file':
                        remote_files[name] = facts
            except Exception:
                # server may not support MLSD or permission issues
                pass
        else:
            # Could not cwd; we'll still attempt uploads by ensuring dirs
            pass

        # Walk local directory, preserving relative subpaths
        for root, _, files in os.walk(local_dir):
            rel_root = os.path.relpath(root, local_dir)
            rel_root = '' if rel_root == '.' else rel_root.replace('\\', '/')
            for file in files:
                if not file.lower().endswith(VALID_EXTENSIONS):
                    continue
                local_file_path = os.path.join(root, file)
                all_local_basenames.add(file)

                remote_name = ALIASES.get(file, file)
                # Preserve subpaths: build remote subpath under remote_dir
                remote_subpath = f"{rel_root}/{remote_name}" if rel_root else remote_name
                remote_file_path = f"{remote_dir.rstrip('/')}/{remote_subpath}"

                local_size = os.path.getsize(local_file_path)
                local_mtime = int(os.path.getmtime(local_file_path))

                sha = None

                # Look for remote entry by basename within remote_files (only listing contains plain names)
                remote_fact = remote_files.get(remote_name)

                # If remote listing exists and file is in same directory (no subdir support in listing),
                # attempt to fetch facts by trying to cwd into the subdir and stat the file
                if rel_root and tried_cwd:
                    # Try to change to subdir to stat
                    try:
                        ftp.cwd(remote_dir.rstrip('/') + '/' + rel_root)
                        try:
                            facts = dict(ftp.mlsd())
                            remote_fact = facts.get(remote_name, remote_fact)
                        except Exception:
                            pass
                        # return to remote_dir afterward
                        ftp.cwd(remote_dir)
                    except Exception:
                        pass

                if remote_fact:
                    remote_size = int(remote_fact.get('size', 0))
                    remote_epoch = parse_mlsd_date(remote_fact.get('modify', ''))
                    protected_remote_paths.add(remote_file_path)

                    if file.lower().endswith('.sav'):
                        # Decide action by conflict policy
                        devcfg = load_device_config(mac) if mac else {}
                        policy = devcfg.get('conflict_policy', cfg.get('bulk_override_policy', 'prompt'))
                        confirm_needed = args.confirm or cfg.get('confirm_on_conflict', True)

                        # Remote newer
                        if remote_epoch > local_mtime:
                            if args.pull_saves:
                                do_pull = False
                                if confirm_needed:
                                    do_pull = confirm_action(f"Pull newer save from 3DS: '{remote_subpath}'", args.confirm, args.dry_run)
                                else:
                                    if policy == 'destination_wins':
                                        do_pull = True
                                    elif policy == 'source_wins':
                                        do_pull = False
                                    else:
                                        do_pull = False
                                if do_pull:
                                    create_save_backup(local_file_path)
                                    parent_remote_dir = os.path.dirname(remote_file_path)
                                    ftp_cwd_safe(ftp, parent_remote_dir)
                                    with open(local_file_path, "wb") as f:
                                        ftp.retrbinary(f"RETR {os.path.basename(remote_file_path)}", f.write)
                                    sha = calculate_sha256(local_file_path)
                                    db.update_entry(sha, local_file_path, remote_file_path)
                                    # archive to cloud
                                    arc = archive_save(local_file_path, remote_subpath)
                                    if arc and args.cloud_sync:
                                        propagate_save_to_cloud_devices(cfg, db, mac, remote_subpath, arc, args.dry_run)
                            elif args.verbose:
                                print(f"Skipped save (Remote is newer, run with --pull-saves to sync): {file}")
                            continue

                        # Local newer
                        elif local_mtime > remote_epoch:
                            do_push = False
                            if confirm_needed:
                                do_push = confirm_action(f"Push newer local save to 3DS: '{remote_subpath}'", args.confirm, args.dry_run)
                            else:
                                if policy == 'source_wins':
                                    do_push = True
                                elif policy == 'destination_wins':
                                    do_push = False
                                else:
                                    do_push = False
                            if do_push:
                                create_save_backup(local_file_path)
                                parent_remote_dir = os.path.dirname(remote_file_path)
                                ensure_remote_dir(ftp, parent_remote_dir)
                                ftp.cwd(parent_remote_dir)
                                with open(local_file_path, "rb") as f:
                                    ftp.storbinary(f"STOR {os.path.basename(remote_file_path)}", f)
                                sha = calculate_sha256(local_file_path)
                                db.update_entry(sha, local_file_path, remote_file_path)
                                # archive to cloud
                                arc = archive_save(local_file_path, remote_subpath)
                                if arc and args.cloud_sync:
                                    propagate_save_to_cloud_devices(cfg, db, mac, remote_subpath, arc, args.dry_run)
                            continue

                    # Non-save files: check DB/hash
                    sha = calculate_sha256(local_file_path)
                    db_entry = db.get_by_sha(sha)
                    if db_entry:
                        old_local = db_entry["local_path"]
                        old_remote = db_entry["remote_path"]
                        if local_file_path != old_local or remote_file_path != old_remote:
                            if confirm_action(f"Rename remote asset from '{os.path.basename(old_remote)}' to '{os.path.basename(remote_file_path)}'", args.confirm, args.dry_run):
                                # try to rename using parent dirs and basenames
                                try:
                                    ftp_cwd_safe(ftp, os.path.dirname(old_remote))
                                    ftp.rename(os.path.basename(old_remote), os.path.basename(remote_file_path))
                                    db.update_entry(sha, local_file_path, remote_file_path)
                                except Exception:
                                    # fallback: check existence of target and decide removal
                                    try:
                                        ftp_cwd_safe(ftp, os.path.dirname(remote_file_path))
                                        if confirm_action(f"Upload new asset to 3DS: '{file}' ({local_size} bytes) (fallback)", args.confirm, args.dry_run):
                                            with open(local_file_path, 'rb') as f:
                                                ftp.storbinary(f"STOR {os.path.basename(remote_file_path)}", f)
                                            db.update_entry(sha, local_file_path, remote_file_path)
                                    except Exception:
                                        print(f"⚠️  Failed to reconcile rename for {file}")
                            continue
                    elif not db_entry and local_size == remote_size:
                        sha = calculate_sha256(local_file_path)
                        if confirm_action(f"Link existing matching remote file to database: '{file}'", args.confirm, args.dry_run):
                            db.update_entry(sha, local_file_path, remote_file_path)
                        continue

                else:
                    # Missing remote file: upload
                    if confirm_action(f"Upload new asset to 3DS: '{remote_subpath}' ({local_size} bytes)", args.confirm, args.dry_run):
                        # ensure remote folder structure exists and upload
                        parent_remote_dir = os.path.dirname(remote_file_path)
                        ensure_remote_dir(ftp, parent_remote_dir)
                        ftp.cwd(parent_remote_dir)
                        with open(local_file_path, "rb") as f:
                            ftp.storbinary(f"STOR {os.path.basename(remote_file_path)}", f)
                        sha = calculate_sha256(local_file_path)
                        db.update_entry(sha, local_file_path, remote_file_path)
                        protected_remote_paths.add(remote_file_path)
                        # archive saves to cloud if it's a save
                        if file.lower().endswith('.sav'):
                            arc = archive_save(local_file_path, remote_subpath)
                            if arc and args.cloud_sync:
                                propagate_save_to_cloud_devices(cfg, db, mac, remote_subpath, arc, args.dry_run)

        # Cleanup orphaned remote files only if clean_remote requested
        if args.clean_remote and remote_files:
            # remote_files keys are basenames from the listed remote_dir
            for rm_name in remote_files.keys():
                # We need to check full possible remote path variants. Simplest: build rm_full_path under remote_dir
                rm_full_path = f"{remote_dir.rstrip('/')}/{rm_name}"
                if rm_full_path in protected_remote_paths:
                    continue
                if rm_name not in all_local_basenames:
                    if confirm_action(f"Delete orphaned remote asset: '{rm_full_path}'", args.confirm, args.dry_run):
                        try:
                            ftp_cwd_safe(ftp, remote_dir)
                            ftp.delete(rm_name)
                        except Exception as e:
                            print(f"❌ Failed to delete remote file {rm_name}: {e}")

    try:
        ftp.quit()
    except Exception:
        pass

    print("==================================================")
    print("✨ Operations completed successfully.")


if __name__ == "__main__":
    main()
