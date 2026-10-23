from dataclasses import dataclass, field


@dataclass
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    fields: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        super().__init__(self.message)


def not_found() -> ApiError:
    return ApiError(404, "RESOURCE_NOT_FOUND", "未找到请求的资源。")


def invalid_reference(message: str = "引用对象不存在或类型不匹配。") -> ApiError:
    return ApiError(422, "INVALID_REFERENCE", message)
