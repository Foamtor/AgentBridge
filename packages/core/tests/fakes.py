"""Shared fakes for core tests (not named conftest — safe under joint pytest)."""

from __future__ import annotations

import asyncio

from agent_base_core.protocol.fragments import OutboundFragment


class FakeCheckpointerFactory:
    async def setup(self) -> None:
        return None

    def is_setup(self) -> bool:
        return True

    async def get(self):
        return None

    async def teardown(self) -> None:
        return None


class FakeRuntime:
    async def astream(self, builder, **kwargs):
        yield OutboundFragment(type="text_delta", data={"content": "ok"})


class SlowCancelRuntime:
    """Blocks until cancel_token is set, then exits."""

    async def astream(self, builder, **kwargs):
        token = kwargs.get("cancel_token")
        yield OutboundFragment(type="text_delta", data={"content": "partial"})
        if isinstance(token, asyncio.Event):
            await token.wait()


class BoomRuntime:
    async def astream(self, builder, **kwargs):
        yield OutboundFragment(type="text_delta", data={"content": "before-fail"})
        raise RuntimeError("boom")


class BadExtensionRuntime:
    async def astream(self, builder, **kwargs):
        yield OutboundFragment(type="x.", data={})
