from typing import Annotated, Literal

import hmac
from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from astrophotoflow.core.errors import ApiError
from astrophotoflow.contracts.common import ErrorEnvelope


bearer = HTTPBearer(auto_error=False)
ERROR_RESPONSES = {
    status: {"model": ErrorEnvelope, "description": description}
    for status, description in {
        401: "Authentication required",
        403: "Origin not allowed by the ComfyUI proxy",
        404: "Resource not found or outside the requested scope",
        405: "Method not allowed",
        409: "Revision conflict",
        422: "Validation error or invalid reference",
        503: "Service not configured or unavailable",
        504: "Service timeout",
        500: "Internal error",
    }.items()
}


async def authenticate(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> None:
    expected = request.app.state.token
    if credentials is None or credentials.scheme.lower() != "bearer" or not hmac.compare_digest(credentials.credentials, expected):
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "需要有效的本机服务令牌。")


def read_session(request: Request):
    with request.app.state.database.read_session() as session:
        yield session


def write_session(request: Request):
    with request.app.state.database.write_session() as session:
        yield session


ReadSession = Annotated[Session, Depends(read_session)]
WriteSession = Annotated[Session, Depends(write_session, scope="function")]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]
SortBy = Annotated[Literal["created_at", "name"], Query()]
Order = Annotated[Literal["asc", "desc"], Query()]
StatusFilter = Annotated[Literal["active", "archived", "all"], Query()]
