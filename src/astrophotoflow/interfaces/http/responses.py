"""HTTP file delivery owns the final release of the acquired data lease."""
from fastapi import Request, Response
from fastapi.responses import FileResponse

from astrophotoflow.contracts.assets import PreviewReference
from astrophotoflow.modules.data.public import read_preview_content


def preview_response(request: Request, reference: PreviewReference, size: str) -> Response:
    content = read_preview_content(request.app.state.database, request.app.state.settings, reference, size)
    return Response(content.content, media_type=content.mime_type)


class LeasedFileResponse(FileResponse):
    def __init__(self, path, release, **kwargs):
        super().__init__(path, **kwargs)
        self.release = release

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.release()

