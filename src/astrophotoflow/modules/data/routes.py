from fastapi import APIRouter

from . import calibration, canvas, content, datasets, equipment, imports, import_batches, import_inspection, library, management_trash, media_view, projects, previews, setups, trash


router = APIRouter()
router.include_router(import_inspection.router)
router.include_router(import_batches.router)
router.include_router(canvas.router)
router.include_router(media_view.router)
for module in (projects, equipment, setups, management_trash, previews, library, trash, imports, datasets, calibration, content):
    router.include_router(module.router)
router.include_router(management_trash.equipment_router)
