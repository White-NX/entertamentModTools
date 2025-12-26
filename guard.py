#!/usr/bin/env python3
"""
file_guard.py
监视单个文件是否被替换/篡改，若检测到则用备份恢复。
Monitor a single file for replacement/tampering and restore from a backup when detected.

支持 --only-once：仅保护一次，首次恢复后立即退出。
Supports `--only-once`: protect only once, exit immediately after the first restore.
"""

import os
import sys
import time
import shutil
import argparse
import hashlib
import threading
import logging
import signal

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except Exception:
    WATCHDOG_AVAILABLE = False

DEFAULT_POLL_INTERVAL = 0.2
READ_CHUNK = 4 * 1024 * 1024

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ---------- 工具函数 / Utilities ----------

def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(READ_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def atomic_copy(src, dst):
    tmp = dst + ".tmp_restore"
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)

# ---------- 文件快照 / File snapshot ----------

class FileSnapshot:
    def __init__(self, path):
        self.path = path
        self.exists = False
        self.inode = None
        self.mtime = None
        self.size = None
        self.hash = None
        self.update()

    def update(self):
        try:
            st = os.stat(self.path)
            self.exists = True
            self.inode = (st.st_ino, st.st_dev)
            self.mtime = st.st_mtime
            self.size = st.st_size
        except FileNotFoundError:
            self.exists = False
            self.inode = None
            self.mtime = None
            self.size = None

    def compute_hash(self):
        if self.exists:
            self.hash = sha256_of_file(self.path)
        else:
            self.hash = None

    def quick_equals(self, other):
        if self.exists != other.exists:
            return False
        if not self.exists:
            return True
        if self.inode != other.inode:
            return False
        if self.mtime != other.mtime or self.size != other.size:
            return False
        return True

# ---------- 核心守护逻辑 / Core guard logic ----------

class FileGuard:
    def __init__(self, target, backup, poll_interval, only_once):
        self.target = os.path.abspath(target)
        self.backup = os.path.abspath(backup) if backup else self.target + ".guardbak"
        self.poll_interval = poll_interval
        self.only_once = only_once
        self._stop = threading.Event()
        self._restored_once = False

        self.snapshot = FileSnapshot(self.target)

        if not os.path.exists(self.backup):
            if not self.snapshot.exists:
                raise FileNotFoundError("Target file not found and no backup provided")
            logging.info("Creating backup file: %s", self.backup)
            shutil.copy2(self.target, self.backup)

        self.backup_hash = sha256_of_file(self.backup)
        logging.info("Backup hash: %s", self.backup_hash)

    def stop(self):
        self._stop.set()

    def _restore(self):
        logging.warning("File tampering detected, restoring from backup")
        atomic_copy(self.backup, self.target)
        self.snapshot.update()
        self.snapshot.compute_hash()
        self._restored_once = True
        logging.info("Restore completed")

    def _check_and_restore(self):
        current = FileSnapshot(self.target)

        if current.quick_equals(self.snapshot):
            return False

        current.compute_hash()

        if current.hash == self.backup_hash:
            self.snapshot = current
            return False

        self._restore()
        self.snapshot = FileSnapshot(self.target)
        self.snapshot.compute_hash()
        return True

    # ---------- watchdog / event-based watcher ----------

    def _start_watchdog(self):
        class Handler(FileSystemEventHandler):
            def __init__(self, guard):
                self.guard = guard

            def on_any_event(self, event):
                if self.guard._check_and_restore():
                    if self.guard.only_once:
                        logging.info("only-once mode: restored once, exiting")
                        self.guard.stop()

        observer = Observer()
        observer.schedule(
            Handler(self),
            os.path.dirname(self.target) or ".",
            recursive=False
        )
        observer.start()

        try:
            while not self._stop.is_set():
                time.sleep(0.3)
        finally:
            observer.stop()
            observer.join()

    # ---------- polling / periodic check loop ----------

    def _start_polling(self):
        while not self._stop.is_set():
            if self._check_and_restore():
                if self.only_once:
                    logging.info("only-once mode: restored once, exiting")
                    break
            time.sleep(self.poll_interval)

    def run(self):
        # 启动即校验一次 / Perform an initial check at startup
        logging.info("Performing initial check")
        self.snapshot.compute_hash()
        if self.snapshot.hash != self.backup_hash:
            self._restore()
            if self.only_once:
                logging.info("only-once mode: restored at startup, exiting")
                return

        logging.info("Entering watch loop")
        if WATCHDOG_AVAILABLE:
            self._start_watchdog()
        else:
            self._start_polling()

# ---------- CLI / Command-line interface ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="Target file to protect")
    parser.add_argument("--backup", "-b", help="Path to backup file")
    parser.add_argument("--poll", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument(
        "--only-once",
        action="store_true",
        help="Protect only once: exit after first restore"
    )
    args = parser.parse_args()

    guard = FileGuard(
        args.target,
        args.backup,
        args.poll,
        args.only_once
    )

    def sig_handler(sig, frame):
        guard.stop()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    guard.run()

if __name__ == "__main__":
    main()
