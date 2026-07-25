#!/usr/bin/env python3
import os
import sys
import ssl
import time
import argparse
import hashlib
import ftplib
import socket
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import json

# --- CONFIGURATION DEFAULTS ---
SCAN_IP_START = "10.0.0.100"
SCAN_IP_END = "10.0.0.129"
FTP_PORT = 5000  # Change to 21 if using standard FTP servers instead of FTPii
TIMEOUT = 3

# Directory Maps: [Local Path, Remote Path]
MAPPINGS = [
    ["/run/media/SN01T/emudeck/Emulation/roms/gb", "/ROMs/gb"],
    ["/run/media/SN01T/emudeck/Emulation/roms/nes", "/ROMs/nes"],
    #["/run/media/SN01T/emudeck/Emulation/roms/nds", "/ROMs/nds"],
]

# Aliases for exact matching legacy name corrections
ALIASES = {
    "Pokemon_Emerald_Patched.gba": "Pokemon - Emerald Version (USA).gba",
    "Pokemon_Emerald_Patched.sav": "Pokemon - Emerald Version (USA).sav"
}

VALID_EXTENSIONS = ('.gba', '.nds', '.sav', '.gb', '.gbc', '.cia')

# Configuration state storage path
CONFIG_DIR = os.path.expanduser("~/.config/deck-console-mgr")
STATE_FILE = os.path.join(CONFIG_DIR, "devices.json")
BACKUP_DIR = os.path.join(CONFIG_DIR, "backups")

os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)


# --- NETWORK & MAC DISCOVERY ENGINE ---
def scan_single_ip(ip):
    """Checks if the chosen port is responsive on a target IP."""
    try:
        with socket.create_connection((ip, FTP_PORT), timeout=1.0):
            return ip
    except (socket.timeout, ConnectionRefusedError, OSError):
        return None

def locate_active_ips():
    """Scans the designated DHCP block in parallel."""
    base_ip = ".".join(SCAN_IP_START.split(".")[:3])
    start_suffix = int(SCAN_IP_START.split(".")[3])
    end_suffix = int(SCAN_IP_END.split(".")[3])
    
    ips_to_scan = [f"{base_ip}.{i}" for i in range(start_suffix, end_suffix + 1)]
    
    active_ips = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        results = executor.map(scan_single_ip, ips_to_scan)
        for res in results:
            if res:
                active_ips.append(res)
    return active_ips

def get_mac_from_proc_arp(target_ip):
    """Reads system ARP translation space to associate MAC addresses without root."""
    if not os.path.exists("/proc/net/arp"):
        return None
    try:
        with open("/proc/net/arp", "r") as f:
            lines = f.readlines()[1:]  # skip header
            for line in lines:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == target_ip:
                    mac = parts[3]
                    if mac != "00:00:00:00:00:00":
                        return mac.lower()
    except Exception:
        pass
    return None

def resolve_device_ip():
    """Scans net tables and pairs your console by its MAC stamp."""
    print("🌐 Scanning network range for console device...")
    active_ips = locate_active_ips()
    if not active_ips:
        print("❌ ERROR: No active FTP endpoints found within specified range.")
        sys.exit(1)
        
    for ip in active_ips:
        mac = get_mac_from_proc_arp(ip)
        if mac:
            # Persistent configuration state management
            state = {}
            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE, "r") as f:
                        state = json.load(f)
                except Exception:
                    pass
            
            if mac not in state:
                state[mac] = {
                    "nickname": f"Console-{mac[-5:].replace(':', '')}",
                    "last_known_ip": ip,
                    "first_seen": datetime.now().isoformat()
                }
                with open(STATE_FILE, "w") as f:
                    json.dump(state, f, indent=2)
            else:
                state[mac]["last_known_ip"] = ip
                with open(STATE_FILE, "w") as f:
                    json.dump(state, f, indent=2)
                    
            print(f"✅ Target Located: {state[mac]['nickname']} ({mac}) at IP {ip}")
            return ip
            
    # Fallback to first found IP if table mapping fails
    print(f"⚠️  Could not confirm MAC mapping. Defaulting to first responsive target: {active_ips[0]}")
    return active_ips[0]


# --- CRYPTO & UTILITIES ---
def calculate_sha256(filepath):
    """Calculates hash signature for data tracking blocks."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

def parse_mlsd_date(modify_str):
    """Translates FTP server MLSD modification string to epoch time."""
    try:
        fmt = "%Y%m%d%H%M%S"
        # Truncate any sub-second or zone symbols if present
        base_str = modify_str.split('.')[0]
        dt = datetime.strptime(base_str[:14], fmt)
        return int(dt.timestamp())
    except Exception:
        return 0

def create_save_backup(local_path):
    """Copies current file array state into storage prior to modification sweeps."""
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


# --- STATE TRACKING INTERFACE ---
class StateDatabase:
    """Manages the internal state mapping db cleanly via JSON."""
    def __init__(self):
        self.db_path = os.path.expanduser("~/.3ds_sync_db.json")
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


# --- INTERACTIVE LOOP CONTROLS ---
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


# --- BANNERS / EXTENSIBILITY STUB ---
def fetch_twilight_assets(local_rom_path):
    """
    Placeholder/Hook for structural expansions.
    Can be configured to pull banner assets/compatibility box arts from GameTDB or GitHub.
    """
    pass


# --- MAIN ENGINE PROCESSING ---
def main():
    parser = argparse.ArgumentParser(description="Steam Deck Console Data Synchronizer")
    parser.add_argument('--apply', action='store_false', dest='dry_run', default=True, help="Enables live modification writes.")
    parser.add_argument('--pull-saves', action='store_true', help="Enables bidirectional sync for .sav assets.")
    parser.add_argument('--clean-remote', action='store_true', help="Removes orphaned files from the target console.")
    parser.add_argument('--confirm', action='store_true', help="Prompts user confirmation before individual operations.")
    parser.add_argument('--verbose', action='store_true', help="Outputs detailed matched and skipped items.")
    args = parser.parse_args()

    print("==================================================")
    print("🔍 DRY-RUN MODE ACTIVE" if args.dry_run else "🚀 LIVE APPLICATION MODE ACTIVE")
    if args.pull_saves: print("📥 Bidirectional Save Sync Enabled (mtime preference)")
    if args.clean_remote: print("🗑  Remote Target Cleanup Sweeps Enabled")
    if args.confirm: print("✋ Interactive Confirmations Active")
    print("==================================================")

    target_ip = resolve_device_ip()
    db = StateDatabase()

    print("Connecting to console FTP file systems...")
    try:
        ftp = ftplib.FTP()
        ftp.connect(target_ip, FTP_PORT, timeout=TIMEOUT)
        ftp.login()
    except Exception as e:
        print(f"❌ FTP Connection Failed: {e}")
        sys.exit(1)

    # Master tracking cache to clean untracked target files safely
    all_local_basenames = set()
    protected_remote_paths = set()

    for local_dir, remote_dir in MAPPINGS:
        if not os.path.isdir(local_dir):
            continue

        if args.verbose:
            print(f"Checking directory: {local_dir} -> {remote_dir}")

        # Extract contents via remote MLSD execution mapping
        remote_files = {}
        try:
            ftp.cwd(remote_dir)
            for name, facts in ftp.mlsd():
                if facts.get('type') == 'file':
                    remote_files[name] = facts
        except Exception:
            # Directory may not exist yet; handle or skip gracefully
            pass

        # Build structural path analysis using generator sweeps
        for root, _, files in os.walk(local_dir):
            for file in files:
                if not file.lower().endswith(VALID_EXTENSIONS):
                    continue
                
                local_file_path = os.path.join(root, file)
                all_local_basenames.add(file)

                # Name translations via alias maps
                remote_name = ALIASES.get(file, file)
                remote_file_path = f"{remote_dir}/{remote_name}"

                local_size = os.path.getsize(local_file_path)
                local_mtime = int(os.path.getmtime(local_file_path))
                
                # Use deferred SHA calculations to keep execution extremely snappy
                sha = None 

                # Look up remote entry
                remote_fact = remote_files.get(remote_name)
                
                if remote_fact:
                    remote_size = int(remote_fact.get('size', 0))
                    remote_epoch = parse_mlsd_date(remote_fact.get('modify', ''))
                    
                    # Track file path as safe from deletion sweeps
                    protected_remote_paths.add(remote_file_path)

                    # SCENARIO 1: Handle Save Files Explicitly
                    if file.lower().endswith('.sav'):
                        if remote_size != local_size or remote_epoch > local_mtime:
                            if args.pull_saves:
                                if confirm_action(f"Pull newer save from 3DS: '{remote_name}'", args.confirm, args.dry_run):
                                    create_save_backup(local_file_path)
                                    with open(local_file_path, "wb") as f:
                                        ftp.retrbinary(f"RETR {remote_file_path}", f.write)
                                    sha = calculate_sha256(local_file_path)
                                    db.update_entry(sha, local_file_path, remote_file_path)
                            elif args.verbose:
                                print(f"Skipped save (Remote is newer, run with --pull-saves to sync): {file}")
                            continue
                        
                        elif local_mtime > remote_epoch:
                            if confirm_action(f"Push newer local save to 3DS: '{file}'", args.confirm, args.dry_run):
                                create_save_backup(local_file_path) # Backup local copy before overriding matching target pairs
                                with open(local_file_path, "rb") as f:
                                    ftp.storbinary(f"STOR {remote_file_path}", f)
                                sha = calculate_sha256(local_file_path)
                                db.update_entry(sha, local_file_path, remote_file_path)
                            continue

                    # SCENARIO 2: Compare Tracking Signatures for Content Shifts
                    sha = calculate_sha256(local_file_path)
                    db_entry = db.get_by_sha(sha)

                    if db_entry:
                        old_local = db_entry["local_path"]
                        old_remote = db_entry["remote_path"]

                        # Check for renames on either end
                        if local_file_path != old_local or remote_file_path != old_remote:
                            if confirm_action(f"Rename remote asset from '{os.path.basename(old_remote)}' to '{remote_name}'", args.confirm, args.dry_run):
                                ftp.rename(old_remote, remote_file_path)
                                db.update_entry(sha, local_file_path, remote_file_path)
                            continue
                    
                    # Light verification matching fallback if hash record is missing
                    elif not db_entry and local_size == remote_size:
                        sha = calculate_sha256(local_file_path)
                        if confirm_action(f"Link existing matching remote file to database: '{file}'", args.confirm, args.dry_run):
                            db.update_entry(sha, local_file_path, remote_file_path)
                        continue

                # SCENARIO 3: Missing / New Files Upload Loops
                else:
                    if confirm_action(f"Upload new asset to 3DS: '{file}' ({local_size} bytes)", args.confirm, args.dry_run):
                        # Ensure remote folder structure exists
                        try:
                            ftp.mkd(remote_dir)
                        except Exception:
                            pass
                        
                        with open(local_file_path, "rb") as f:
                            ftp.storbinary(f"STOR {remote_file_path}", f)
                        
                        sha = calculate_sha256(local_file_path)
                        db.update_entry(sha, local_file_path, remote_file_path)
                        protected_remote_paths.add(remote_file_path)

        # SCENARIO 4: Remote Directory Orphans Cleanup Engine
        if args.clean_remote and remote_files:
            for rm_name in remote_files.keys():
                rm_full_path = f"{remote_dir}/{rm_name}"
                if rm_full_path in protected_remote_paths:
                    continue
                
                # Safety checks: Don't wipe if the file exists under any local map scheme
                if rm_name not in all_local_basenames:
                    if confirm_action(f"Delete orphaned remote asset: '{rm_full_path}'", args.confirm, args.dry_run):
                        try:
                            ftp.delete(rm_full_path)
                        except Exception as e:
                            print(f"❌ Failed to delete remote file {rm_name}: {e}")

    ftp.quit()
    print("==================================================")
    print("✨ Operations completed successfully.")

if __name__ == "__main__":
    main()
