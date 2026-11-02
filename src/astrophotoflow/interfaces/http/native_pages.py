"""Authenticate native page messages and route software confirmations."""

from fastapi import Depends, FastAPI

from astrophotoflow.contracts.native import NativePageEvent, NativePageReply
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import exception_error, localized_error, workspace_locale
from astrophotoflow.interfaces.http.dependencies import authenticate


def register_native_pages(app: FastAPI, settings: Settings) -> None:
    @app.post("/internal/native/page", response_model=NativePageReply, dependencies=[Depends(authenticate)], include_in_schema=False)
    async def receive_native_page(body: NativePageEvent):
        if body.action == "open":
            with app.state.software_action_lock:
                app.state.software_page_tokens[body.page_id] = body.page_token
            return NativePageReply(
                event_id=body.event_id, page_id=body.page_id, page_token=body.page_token, result=None, error=None,
            )
        if body.action == "close":
            with app.state.software_action_lock:
                if app.state.software_page_tokens.get(body.page_id) == body.page_token:
                    app.state.software_page_tokens.pop(body.page_id, None)
            return NativePageReply(
                event_id=body.event_id, page_id=body.page_id, page_token=body.page_token, result=None, error=None,
            )
        with app.state.software_action_lock:
            page_is_current = app.state.software_page_tokens.get(body.page_id) == body.page_token
        if not page_is_current:
            return NativePageReply(
                event_id=body.event_id, page_id=body.page_id, page_token=body.page_token, result=None,
                error=localized_error(workspace_locale(settings.workspace), 'NATIVE_PAGE_EXPIRED', 'confirmation_page_expired'),
            )
        handler = getattr(app.state, "confirm_software_action", None)
        if handler is None:
            return NativePageReply(
                event_id=body.event_id, page_id=body.page_id, page_token=body.page_token, result=None,
                error=localized_error(workspace_locale(settings.workspace), 'SOFTWARE_ACTION_EXPIRED', 'no_pending_software_action'),
            )
        try:
            result = await handler(body.payload, page_id=body.page_id, page_token=body.page_token)
        except ApiError as exc:
            return NativePageReply(
                event_id=body.event_id, page_id=body.page_id, page_token=body.page_token, result=None,
                error=exception_error(workspace_locale(settings.workspace), exc, code='INTERNAL_ERROR', message_key='software_install_or_definition_write_failed'),
            )
        return NativePageReply(
            event_id=body.event_id, page_id=body.page_id, page_token=body.page_token, result=result, error=None,
        )
