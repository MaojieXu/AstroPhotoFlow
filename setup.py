from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py


ROOT = Path(__file__).resolve().parent


class build_py(_build_py):
    def run(self):
        package = Path(self.build_lib) / "astrophotoflow"
        if package.exists():
            shutil.rmtree(package)
        super().run()
        target = Path(self.build_lib) / "astrophotoflow" / "web"
        shutil.copytree(ROOT / "build" / "frontend", target, dirs_exist_ok=True)

    def get_outputs(self, include_bytecode=1):
        outputs = super().get_outputs(include_bytecode)
        assets = Path(self.build_lib) / "astrophotoflow" / "web"
        outputs.extend(str(path) for path in assets.rglob("*") if path.is_file())
        return outputs


if __name__ == "__main__":
    setup(cmdclass={"build_py": build_py}, options={"build": {"build_base": "build/python"}})
