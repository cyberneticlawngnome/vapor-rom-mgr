# vapor-rom-mgr — 3DS/Steam Deck sync helper (refactor)

This branch continues the refactor of 3ds-sync to implement cloud-save propagation and conflict policies.

What's new

- Cloud save archive: archived copies of .sav files are stored in `~/.config/deck-console-mgr/cloud_saves/` preserving relative paths.
- Per-device opt-in cloud sharing: set `"cloud_share": true` in the device JSON to allow propagation.
- Conflict policy per-device: `conflict_policy` can be `prompt`, `source_wins`, or `destination_wins`.
- New CLI flag `--cloud-sync` to trigger propagation of archived saves to other devices that opted into cloud sharing.

Sample device config: `~/.config/deck-console-mgr/devices/aabbccddeeff.json`

Notes & limitations

- Cloud propagation attempts to connect to each device's last_known_ip stored in the device JSON and upload the save file. This is a simple approach and may fail if devices are not reachable on the network at the time of propagation.
- By default the tool runs in dry-run mode. Use `--apply` to enable live writes.
- This initial implementation focuses on a conservative, user-confirmation-first workflow. Further automation (daemon mode, scheduled background sync) can be implemented later.

