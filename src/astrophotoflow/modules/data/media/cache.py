import shutil
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from time import monotonic

MEMORY_BYTES = 256 * 1024**2
DISK_BYTES = 4 * 1024**3


class MediaCache:
    def __init__(self, data_dir, disk_budget=DISK_BYTES, memory_budget=MEMORY_BYTES):
        self.data_dir, self.disk_budget, self.memory_budget = (data_dir.resolve(), disk_budget, memory_budget)
        self.lock = RLock()
        self.active = {}
        self.memory = OrderedDict()
        self.memory_bytes = 0
        self.disk_files = {}
        self.disk_folders = {}
        self.reconciled_at = None

    @contextmanager
    def hold(self, folder):
        folder.resolve().relative_to(self.data_dir / "previews")
        with self.lock:
            if self.reconciled_at is None or monotonic() - self.reconciled_at >= 300:
                self.reconcile()
            self.active[folder] = self.active.get(folder, 0) + 1
        try:
            yield
        finally:
            with self.lock:
                self.active[folder] -= 1
                if not self.active[folder]:
                    del self.active[folder]

    def folders(self):
        return list((self.data_dir / "previews").glob("*/media/*"))

    def reconcile(self):
        with self.lock:
            files, folders = ({}, {})
            for folder in self.folders():
                amount = 0
                for path in folder.rglob("*"):
                    if path.is_file():
                        files[path] = path.stat().st_size
                        amount += files[path]
                folders[folder] = (amount, folder.stat().st_mtime_ns)
            self.disk_files, self.disk_folders = (files, folders)
            self.reconciled_at = monotonic()

    def record(self, path):
        path = path.resolve()
        relative = path.relative_to(self.data_dir / "previews")
        if len(relative.parts) < 4 or relative.parts[1] != "media":
            raise ValueError("Display cache must be inside a asset media directory.")
        folder = self.data_dir / "previews" / Path(*relative.parts[:3])
        with self.lock:
            if self.reconciled_at is None:
                self.reconcile()
            size = path.stat().st_size if path.is_file() else 0
            old = self.disk_files.get(path, 0)
            amount, modified = self.disk_folders.get(folder, (0, 0))
            if size:
                self.disk_files[path] = size
            else:
                self.disk_files.pop(path, None)
            self.disk_folders[folder] = (amount + size - old, folder.stat().st_mtime_ns if folder.exists() else modified)

    def reserve(self, size):
        with self.lock:
            if size > self.disk_budget:
                raise ValueError("当前显示数据超过4GiB缓存预算；原件保留，未发布缩小替代图。")
            if self.reconciled_at is None:
                self.reconcile()
            total = sum((amount for amount, _ in self.disk_folders.values()))
            for folder, (amount, _) in sorted(self.disk_folders.items(), key=lambda item: item[1][1]):
                if total + size <= self.disk_budget:
                    break
                if folder in self.active:
                    continue
                folder.resolve().relative_to(self.data_dir / "previews")
                if folder.exists():
                    shutil.rmtree(folder)
                del self.disk_folders[folder]
                self.disk_files = {path: size for path, size in self.disk_files.items() if not path.is_relative_to(folder)}
                total -= amount
            if total + size > self.disk_budget or shutil.disk_usage(self.data_dir).free < size:
                raise ValueError("可用显示缓存或磁盘空间不足；请关闭其他查看窗口后重试。")

    def get(self, key):
        with self.lock:
            value = self.memory.get(key)
            if value is not None:
                self.memory.move_to_end(key)
            return value

    def put(self, key, value):
        with self.lock:
            previous = self.memory.pop(key, None)
            self.memory_bytes -= len(previous) if previous is not None else 0
            if len(value) > self.memory_budget:
                return
            self.memory[key] = value
            self.memory_bytes += len(value)
            while self.memory_bytes > self.memory_budget:
                _, removed = self.memory.popitem(last=False)
                self.memory_bytes -= len(removed)

    def write(self, path, content):
        path = path.resolve()
        relative = path.relative_to(self.data_dir / "previews")
        if len(relative.parts) < 4 or relative.parts[1] != "media":
            raise ValueError("Display cache must be inside a asset media directory.")
        with self.lock:
            if self.reconciled_at is None:
                self.reconcile()
            self.reserve(max(0, len(content) - self.disk_files.get(path, 0)))
            temporary = path.with_suffix(path.suffix + ".part")
            temporary.write_bytes(content)
            temporary.replace(path)
            self.record(path)


def media_locations(preview, settings):
    if not preview.storage_path or Path(preview.storage_path).name != "manifest.json":
        return []
    manifest = (settings.data_dir / preview.storage_path).resolve()
    manifest.relative_to((settings.data_dir / "previews").resolve())
    return [str(path.relative_to(settings.data_dir)) for path in manifest.parent.rglob("*") if path.is_file()]
