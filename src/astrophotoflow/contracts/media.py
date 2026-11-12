from typing import Literal
from pydantic import ConfigDict, Field, FiniteFloat, field_validator, model_validator
from astrophotoflow.contracts.common import StrictModel, UuidInput, optional_response_fields
from astrophotoflow.contracts.previews import PreviewIssue
DisplayChannel = Literal['composite', 'red', 'green', 'blue']

class MediaSelection(StrictModel):
    dataset_id: UuidInput | None = None
    prefetch: bool = False
    consumer_id: str | None = Field(default=None, max_length=64)
    generation: int = Field(default=0, ge=0)
    hdu_index: int | None = Field(default=None, ge=0)
    array_key: str | None = None
    x_axis: int | None = Field(default=None, ge=0)
    y_axis: int | None = Field(default=None, ge=0)
    channel_axis: int | None = Field(default=None, ge=0)
    slices: dict[str, int] = Field(default_factory=dict)
    frame_index: int | None = Field(default=None, ge=0)
    media_time: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    playback_key: str | None = None
    proxy: bool = False
    display_range: tuple[FiniteFloat, FiniteFloat] | None = None
    display_balance: Literal['auto', 'preserve'] | None = None
    preview_max_edge: Literal[512, 1024, 2048] | None = 1024
    channel: DisplayChannel = 'composite'

    @field_validator('display_range', mode='before')
    @classmethod
    def display_range_from_wire(cls, value):
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode='after')
    def valid_axes(self):
        axes = [axis for axis in (self.x_axis, self.y_axis, self.channel_axis) if axis is not None]
        if len(axes) != len(set(axes)) or any((not axis.isascii() or not axis.isdecimal() or index < 0 for axis, index in self.slices.items())):
            raise ValueError('显示轴必须不同，切片索引不能为负。')
        if self.media_time is not None and self.frame_index is not None:
            raise ValueError('只能用帧编号或呈现时间戳定位一帧。')
        if self.display_range is not None and (not self.display_range[0] < self.display_range[1]):
            raise ValueError('显示阈值需要有限且递增的上下限。')
        return self

class MediaArray(StrictModel):
    key: str
    shape: list[int]
    dtype: str
    numeric: bool

class MediaHdu(StrictModel):
    index: int = Field(ge=0)
    name: str | None = None
    shape: list[int]
    kind: str | None = None

class MediaState(StrictModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True, json_schema_extra=optional_response_fields('channels'))
    key: str
    status: Literal['generating', 'available', 'failed', 'unsupported']
    phase: Literal['queued', 'preparing'] | None = None
    kind: Literal['image', 'video'] = 'image'
    width: int = 0
    height: int = 0
    max_level: int = 0
    tile_size: int = 512
    selection: MediaSelection = Field(default_factory=MediaSelection)
    arrays: list[MediaArray] = Field(default_factory=list)
    hdus: list[MediaHdu] = Field(default_factory=list)
    needs_selection: bool = False
    overview_url: str | None = None
    tile_url: str | None = None
    video_url: str | None = None
    mime_type: str | None = None
    proxy: bool = False
    frame_index: int | None = None
    media_time: float | None = None
    frame_count: int | None = None
    duration: float | None = None
    note: str | None = None
    display_recipe: dict | None = None
    error: PreviewIssue | None = None
    channels: list[DisplayChannel] = Field(default_factory=list, exclude_if=lambda channels: not channels)
