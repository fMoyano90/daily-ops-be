import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.config import settings
from app.models.project import Project, ProjectType
from app.models.task import Task, TaskSource, TaskStatus, Priority

PROJECTS = [
    {"name": "SMU", "type": ProjectType.work, "color": "#3b82f6"},
    {"name": "Núcleo Gestor", "type": ProjectType.business, "color": "#8b5cf6"},
    {"name": "SubTech", "type": ProjectType.business, "color": "#06b6d4"},
    {"name": "SubVitals", "type": ProjectType.business, "color": "#10b981"},
    {"name": "Wingenroth", "type": ProjectType.partner, "color": "#f59e0b"},
    {"name": "Familia", "type": ProjectType.personal, "color": "#ec4899"},
    {"name": "Salud", "type": ProjectType.personal, "color": "#ef4444"},
    {"name": "Pareja", "type": ProjectType.personal, "color": "#f97316"},
]


async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        async with session.begin():
            for proj_data in PROJECTS:
                project = Project(**proj_data)
                session.add(project)
            print(f"Seeded {len(PROJECTS)} projects")

    await engine.dispose()
    print("Seed completed!")


if __name__ == "__main__":
    asyncio.run(seed())
