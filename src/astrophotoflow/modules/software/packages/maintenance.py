"""Serialize concrete package maintenance."""
import asyncio
from contextlib import asynccontextmanager

from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software import bundles

PACKAGE_LOCKS: dict[str, asyncio.Lock] = {}


@asynccontextmanager
async def maintain_package(package_id: str):
    bundles.release(package_id)
    lock = PACKAGE_LOCKS.setdefault(package_id, asyncio.Lock())
    if lock.locked():
        raise ApiError(409, "SOFTWARE_BUSY", "软件包当前正在维护。", message_key='the_software_package_is_undergoing_maintenance')
    await lock.acquire()
    try:
        yield
    finally:
        lock.release()
