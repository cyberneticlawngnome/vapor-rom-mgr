"""Vapor ROM Manager CLI entry point."""

import argparse
import sys
from .rom_manager import ROMManager


def _list_devices(mgr: ROMManager) -> None:
    devices = mgr.detect_devices()
    if not devices:
        print("No devices configured.")
        return
    for dev_id, info in devices.items():
        status = "ONLINE" if info["online"] else "OFFLINE"
        name = info["plugin"].device_name
        print(f"  {dev_id:<20} {status:<10} {name}")


def _cmd_detect(args) -> None:
    mgr = ROMManager(config_dir=args.config)
    print("Devices:")
    _list_devices(mgr)


def _cmd_sync(args) -> None:
    mgr = ROMManager(config_dir=args.config)
    mgr.detect_devices()

    if args.device:
        device_ids = [args.device]
    else:
        # Sync all online devices
        device_ids = [d for d, i in mgr.devices.items() if i["online"]]
        if not device_ids:
            print("No online devices found. Use --device <id> to target one.")
            sys.exit(1)

    dry_run = not args.apply
    for dev_id in device_ids:
        result = mgr.sync_device(dev_id, dry_run=dry_run)
        _print_sync_result(result)


def _cmd_scan_assets(args) -> None:
    mgr = ROMManager(config_dir=args.config)
    mgr.detect_devices()

    if not args.device:
        print("specify --device <id>")
        sys.exit(1)

    dry_run = not args.apply
    result = mgr.scan_assets(args.device, dry_run=dry_run)
    _print_asset_result(result)


def _cmd_validate(args) -> None:
    mgr = ROMManager(config_dir=args.config)

    device_ids = [args.device] if args.device else list(mgr.config["devices"].keys())
    for dev_id in device_ids:
        results = mgr.validate_roms(dev_id)
        invalid = [r for r in results if not r.get("valid", True)]
        total = len(results)
        print(f"{dev_id}: {total - len(invalid)}/{total} valid" + (
            f" ({len(invalid)} invalid)" if invalid else ""))
        if args.verbose and invalid:
            for r in invalid:
                print(f"  SKIP {r['rom']}: {r.get('reason', '?')}")


def _print_sync_result(result: dict) -> None:
    rom = result.get("rom_sync", {})
    assets = result.get("asset_push", {})
    err = result.get("error")
    if err:
        print(f"  ERROR: {err}")
        return
    print(f"  ROMs: synced={rom.get('synced', 0)} skipped={rom.get('skipped', 0)} failed={rom.get('failed', 0)}")
    print(f"  Assets: pushed={assets.get('pushed', 0)} skipped={assets.get('skipped', 0)} failed={assets.get('failed', 0)}")


def _print_asset_result(result: dict) -> None:
    err = result.get("error")
    if err:
        print(f"  ERROR: {err}")
        return
    print(f"  pushed={result.get('pushed', 0)} skipped={result.get('skipped', 0)} failed={result.get('failed', 0)}")


def main() -> None:
    p = argparse.ArgumentParser(prog="vapor", description="ROM & asset manager for flash carts")
    p.add_argument("--config", type=argparse.Path, default=None, help="Config directory (default: ./config)")

    sub = p.add_subparsers(dest="command")

    sub.add_parser("detect", help="Scan for connected devices")

    s = sub.add_parser("sync", help="Sync ROMs and push assets")
    s.add_argument("--device", help="Device ID (sync all online if omitted)")
    s.add_argument("--apply", action="store_true", help="Actually write files (default: dry-run)")

    s = sub.add_parser("scan-assets", help="Scan for missing icons and optionally push")
    s.add_argument("--device", required=True, help="Device ID")
    s.add_argument("--apply", action="store_true", help="Actually push icons (default: dry-run)")

    s = sub.add_parser("validate", help="Validate ROMs against device capabilities")
    s.add_argument("--device", help="Device ID (all devices if omitted)")
    s.add_argument("-v", "--verbose", action="store_true", help="Show invalid ROM details")

    args = p.parse_args()
    if not args.command:
        p.print_help()
        sys.exit(0)

    cmds = {
        "detect": _cmd_detect,
        "sync": _cmd_sync,
        "scan-assets": _cmd_scan_assets,
        "validate": _cmd_validate,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
