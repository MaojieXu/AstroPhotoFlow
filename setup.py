from pathlib import Path
import shutil

from setuptools.command.build_py import build_py as _build_py


ROOT = Path(__file__).parent


class build_py(_build_py):
    def run(self):
        super().run()
        service_target = Path(self.build_lib) / "astrophotoflow_service"
        shutil.copy2(ROOT / "service" / "alembic.ini", service_target / "alembic.ini")
        shutil.copytree(ROOT / "service" / "alembic", service_target / "alembic", dirs_exist_ok=True)

        comfy_node = Path(self.build_lib) / "astrophotoflow" / "comfy_node"
        comfy_node.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "src" / "astrophotoflow" / "comfy_node" / "__init__.py", comfy_node / "__init__.py")
        shutil.copytree(ROOT / "web", comfy_node / "web", dirs_exist_ok=True)

    def get_outputs(self, include_bytecode=1):
        outputs = super().get_outputs(include_bytecode)
        for relative in ("astrophotoflow_service/alembic.ini", "astrophotoflow/comfy_node/__init__.py"):
            outputs.append(str(Path(self.build_lib) / relative))
        for directory in (
            Path(self.build_lib) / "astrophotoflow_service" / "alembic",
            Path(self.build_lib) / "astrophotoflow" / "comfy_node" / "web",
        ):
            outputs.extend(str(path) for path in directory.rglob("*") if path.is_file())
        return outputs


if __name__ == "__main__":
    from setuptools import setup

    setup(cmdclass={"build_py": build_py})
