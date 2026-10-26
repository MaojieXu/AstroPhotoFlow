from pathlib import Path
import os
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py
from setuptools.command.egg_info import egg_info as _egg_info


ROOT = Path(__file__).resolve().parent


class egg_info(_egg_info):
    def find_sources(self):
        super().find_sources()
        generated = {"node_modules", ".git", "__pycache__", ".cache", ".vite", ".astro", "coverage", "playwright-report", "test-results", "dist", "dist-ssr"}
        for directory, folders, files in os.walk(ROOT / "frontend", followlinks=False):
            folders[:] = [name for name in folders if name not in generated]
            for name in files:
                if name.endswith((".pyc", ".pyo", ".pyd")) or name == ".env" or (name.startswith(".env.") and not name.endswith(".example")):
                    continue
                self.filelist.append(str((Path(directory) / name).relative_to(ROOT)))
        self.filelist.sort()
        self.filelist.remove_duplicates()
        manifest = Path(self.egg_info) / "SOURCES.txt"
        manifest.write_text("\n".join(Path(name).as_posix() for name in self.filelist.files) + "\n", encoding="utf-8")


class build_py(_build_py):
    def run(self):
        package = Path(self.build_lib) / "astrophotoflow"
        if package.exists():
            shutil.rmtree(package)
        super().run()
        target = Path(self.build_lib) / "astrophotoflow" / "web"
        shutil.copytree(ROOT / ".artifacts" / "build" / "frontend", target, dirs_exist_ok=True)

    def get_outputs(self, include_bytecode=1):
        outputs = super().get_outputs(include_bytecode)
        assets = Path(self.build_lib) / "astrophotoflow" / "web"
        outputs.extend(str(path) for path in assets.rglob("*") if path.is_file())
        return outputs


if __name__ == "__main__":
    setup(cmdclass={"build_py": build_py, "egg_info": egg_info}, options={"build": {"build_base": ".artifacts/build/python"}})
