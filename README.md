# entertamentModTools

## About guard.py

**I strongly suggest thtat using watchdog because its speed.**

- Summary:
  - `file_guard.py` monitors a single target file for replacement or tampering, and restores it from a backup when changes are detected.
  - It supports event-driven monitoring (via `watchdog`) and a polling fallback.

- Usage examples:

```bash
# Protect target.txt, use default backup target.txt.guardbak, poll every 0.2s
python guard.py target.txt

# Use a specific backup file
python guard.py target.txt --backup /path/to/backup.bak

# Restore only once then exit
python guard.py target.txt --only-once
```

- Notes:
  - The program performs an initial integrity check at startup and will restore if the target differs from the backup.
  - If `watchdog` is installed, the program prefers the event-based watcher to reduce overhead.
