from typing import Annotated, Literal

from pydantic import Field

from astrophotoflow.contracts.common import StrictModel, UuidInput


class ThumbnailAssetTarget(StrictModel):
    kind: Literal["asset"]
    asset_id: UuidInput
    asset_version_id: UuidInput


class ThumbnailDatasetTarget(StrictModel):
    kind: Literal["dataset"]
    dataset_id: UuidInput
    dataset_version_id: UuidInput


class ThumbnailLibraryTarget(StrictModel):
    kind: Literal["library_missing"]


ThumbnailTarget = Annotated[
    ThumbnailAssetTarget | ThumbnailDatasetTarget | ThumbnailLibraryTarget,
    Field(discriminator="kind"),
]


class ThumbnailBatchCreate(StrictModel):
    request_id: UuidInput
    target: ThumbnailTarget
    mode: Literal["missing", "rebuild"] = "missing"


class ThumbnailRetry(StrictModel):
    item_ids: list[UuidInput] = Field(min_length=1, max_length=200)


class ThumbnailBatchItemOut(StrictModel):
    id: UuidInput
    asset_version_id: UuidInput | None
    dataset_version_id: UuidInput | None
    position: int
    status: Literal["queued", "generating", "available", "failed", "unsupported", "deleted"]
    error: str | None


class ThumbnailGroupFailure(StrictModel):
    dataset_version_id: UuidInput
    reference_asset_version_id: UuidInput
    code: Literal["FIRST_FRAME_UNAVAILABLE"]
    error: str


class ThumbnailBatchOut(StrictModel):
    request_id: UuidInput
    target: ThumbnailTarget
    state: Literal["running", "completed", "needs_attention"]
    total: int
    queued: int
    generating: int
    available: int
    failed: int
    unsupported: int
    deleted: int
    group_failures: list[ThumbnailGroupFailure]
    items: list[ThumbnailBatchItemOut]
    limit: int
    offset: int
