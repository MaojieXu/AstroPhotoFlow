from datetime import datetime
from math import isfinite
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_serializer

UuidInput = Annotated[UUID, Field(strict=False)]
JsonObject = dict[str, JsonValue]


CfaPattern = Literal["MONO", "RGGB", "BGGR", "GRBG", "GBRG", "XTRANS", "QUAD_BAYER"]


EquipmentKind = Literal["camera", "telescope", "filter", "mount"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_serializer(mode="wrap")
    def serialize_utc(self, handler):
        serialized = handler(self)
        if isinstance(serialized, dict):
            for field_name, field_value in self:
                value = serialized.get(field_name)
                if isinstance(field_value, datetime) and isinstance(value, str) and value.endswith("+00:00"):
                    serialized[field_name] = value[:-6] + "Z"
        return serialized


class SnapshotModel(StrictModel):
    """Keep missing facts distinct from explicitly recorded null values."""

    @model_serializer(mode="wrap")
    def serialize_snapshot(self, handler, info):
        serialized = self.serialize_utc(handler)
        result = {name: value for name, value in serialized.items() if name in self.model_fields_set}
        for name, value in self:
            if name in result and isinstance(value, BaseModel):
                result[name] = value.model_dump(mode=info.mode, exclude_unset=True)
        return result


class PageMetadata(StrictModel):
    """Shared response bounds for the platform's limit/offset pages."""

    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


def check_name(value: str) -> str:
    if not value.strip():
        raise ValueError("名称不能为空或仅含空白。")
    return value


def finite(value: float | None) -> float | None:
    if value is not None and not isfinite(value):
        raise ValueError("数值必须是有限值。")
    return value


class ErrorDetail(StrictModel):
    code: str
    message: str
    fields: list[dict[str, str]]


class ErrorEnvelope(StrictModel):
    error: ErrorDetail
    request_id: UUID
