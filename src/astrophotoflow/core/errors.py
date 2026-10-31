from dataclasses import dataclass, field


@dataclass
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    fields: list[dict[str, str]] = field(default_factory=list)
    message_key: str | None = None
    message_params: dict[str, str | int | float] = field(default_factory=dict)
    field_message_keys: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__(self.message)


def not_found() -> ApiError:
    return ApiError(404, "RESOURCE_NOT_FOUND", "未找到请求的资源。", message_key='the_requested_resource_was_not_found')


def invalid_reference(message: str = "引用对象不存在或类型不匹配。", *, message_key: str | None = None,
                      message_params: dict[str, str | int | float] | None = None) -> ApiError:
    return ApiError(422, "INVALID_REFERENCE", message, message_key=message_key, message_params=message_params or {})
