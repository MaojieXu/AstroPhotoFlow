import shutil
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

MEMORY_BYTES = 256 * 1024**2
DISK_BYTES = 4 * 1024**3


class MediaCache:
    def __init__(self, data_dir, disk_budget=DISK_BYTES, memory_budget=MEMORY_BYTES):
        self.data_dir, self.disk_budget, self.memory_budget = data_dir.resolve(), disk_budget, memory_budget
        self.lock = RLock()
        self.active = {}
        self.memory = OrderedDict()
        self.memory_bytes = 0

    @contextmanager
    def hold(self, folder):
        folder.resolve().relative_to(self.data_dir / "previews")
        with self.lock:
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

    def reserve(self, size):
        with self.lock:
            if size > self.disk_budget:
                raise ValueError("当前显示数据超过4GiB缓存预算；原件保留，未发布缩小替代图。")
            folders = self.folders()
            total = sum(path.stat().st_size for folder in folders for path in folder.rglob("*") if path.is_file())
            for folder in sorted(folders, key=lambda item: item.stat().st_mtime_ns):
                if total + size <= self.disk_budget:
                    break
                if folder in self.active:
                    continue
                folder.resolve().relative_to(self.data_dir / "previews")
                amount = sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())
                shutil.rmtree(folder)
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
        self.reserve(len(content))
        temporary = path.with_suffix(path.suffix + ".part")
        temporary.write_bytes(content)
        temporary.replace(path)


def media_locations(preview, settings):
    if not preview.storage_path or Path(preview.storage_path).name != 'manifest.json':
        return []
    manifest = (settings.data_dir / preview.storage_path).resolve()
    manifest.relative_to((settings.data_dir / "previews").resolve())
    return [str(path.relative_to(settings.data_dir)) for path in manifest.parent.rglob("*") if path.is_file()]
