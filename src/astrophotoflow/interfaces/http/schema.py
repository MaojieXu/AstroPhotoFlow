"""Include real native message DTOs in the shared contract without inventing routes."""

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from pydantic import TypeAdapter

from astrophotoflow.contracts.canvas import (
    NativeCanvasCommand,
    NativeCanvasEvent,
    NativeCanvasGraphCommand,
    NativeCanvasMessage,
)
from astrophotoflow.contracts.native import NativePageEvent, NativePageReply


def register_native_schemas(app: FastAPI) -> None:
    base_openapi = app.openapi
    messages = {
        "NativeCanvasCommand": NativeCanvasCommand,
        "NativeCanvasGraphCommand": NativeCanvasGraphCommand,
        "NativeCanvasEvent": NativeCanvasEvent,
        "NativeCanvasMessage": NativeCanvasMessage,
        "NativePageEvent": NativePageEvent,
        "NativePageReply": NativePageReply,
    }

    def openapi():
        document = base_openapi()
        if "x-apf-native-messages" in document:
            return document
        components = document.setdefault("components", {}).setdefault("schemas", {})
        for name, message in messages.items():
            schema = jsonable_encoder(
                TypeAdapter(message).json_schema(
                    mode="serialization", ref_template="#/components/schemas/{model}"
                ),
                exclude_none=True,
            )
            definitions = schema.pop("$defs", {})
            definitions[name] = schema
            for key, value in definitions.items():
                if key in components and components[key] != value:
                    raise ValueError(f"Conflicting native message schema: {key}")
                components[key] = value
        document["x-apf-native-messages"] = sorted(messages)
        return document

    app.openapi = openapi
