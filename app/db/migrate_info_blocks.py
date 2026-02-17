from __future__ import annotations

import asyncio
import json
from copy import deepcopy

from sqlalchemy import select

from app.db.models_project import Project
from app.db.session import async_session, init_models
from app.routers.project import PROJECT_INFO_BLOCKS


def _default_blocks(lang: str) -> list[dict]:
    blocks = PROJECT_INFO_BLOCKS.get(lang)
    if not blocks:
        raise RuntimeError(f"Missing default project info blocks for language '{lang}'")
    return [b.model_dump() for b in deepcopy(blocks)]


async def migrate_info_blocks() -> None:
    await init_models()
    default_en = _default_blocks("en")
    default_de = _default_blocks("de")

    total = 0
    migrated = 0
    skipped = 0

    async with async_session() as session:
        res = await session.execute(select(Project))
        projects = res.scalars().all()
        total = len(projects)

        for project in projects:
            changed = False
            if not project.info_blocks_en:
                project.info_blocks_en = deepcopy(default_en)
                changed = True
            if not project.info_blocks_de:
                project.info_blocks_de = deepcopy(default_de)
                changed = True

            if changed:
                migrated += 1
                print(f"[migrated] slug={project.slug}")
            else:
                skipped += 1
                print(f"[skipped] slug={project.slug}")

        await session.commit()

    summary = {
        "total_projects": total,
        "migrated_projects": migrated,
        "skipped_projects": skipped,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(migrate_info_blocks())
