from __future__ import annotations

import asyncio

from app.db.session import init_models


async def _main() -> None:
    await init_models()


if __name__ == "__main__":
    asyncio.run(_main())
