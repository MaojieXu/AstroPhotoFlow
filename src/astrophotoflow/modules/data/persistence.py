"""Explicit model assembly for the database schema during staged refactoring."""

from sqlalchemy import MetaData

from astrophotoflow.core.database.base import Base
from astrophotoflow.modules.data.assets import models as asset_models  # noqa: F401 -- register owned mappings
from astrophotoflow.modules.data.calibration import models as calibration_models  # noqa: F401 -- register owned mappings
from astrophotoflow.modules.data.datasets import models as dataset_models  # noqa: F401 -- register owned mappings
from astrophotoflow.modules.data.equipment import models as equipment_models  # noqa: F401 -- register owned mappings
from astrophotoflow.modules.data.imports import models as import_models  # noqa: F401 -- register owned mappings
from astrophotoflow.modules.data.media import models as media_models  # noqa: F401 -- register owned mappings
from astrophotoflow.modules.data.projects import models as project_models  # noqa: F401 -- register owned mappings
from astrophotoflow.modules.data.trash import models as trash_models  # noqa: F401 -- register owned mappings


def schema_metadata() -> MetaData:
    return Base.metadata
