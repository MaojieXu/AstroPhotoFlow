from fastapi import APIRouter

from . import calibration, datasets, equipment, imports, library, management_trash, projects, previews, setups, trash


router = APIRouter()
for module in (projects, equipment, setups, management_trash, previews, library, trash, imports, datasets, calibration):
    router.include_router(module.router)
