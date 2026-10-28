from fastapi import APIRouter

from . import calibration, content, datasets, equipment, imports, library, management_trash, projects, previews, setups, trash


router = APIRouter()
for module in (projects, equipment, setups, management_trash, previews, library, trash, imports, datasets, calibration, content):
    router.include_router(module.router)
