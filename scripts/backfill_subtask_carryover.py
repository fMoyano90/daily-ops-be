"""One-shot backfill: copy subtasks from each prior DailyTask into the matching
DailyTask of today's plan when today's task has no subtasks yet.

Run from fastapi-project/ with the same env as the app:
    python3 -m scripts.backfill_subtask_carryover           # only today's plans
    python3 -m scripts.backfill_subtask_carryover --all     # every plan that is missing carry-over
"""
import asyncio
import sys
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.daily_plan import DailyPlan
from app.models.daily_task import DailyTask
from app.services.subtask_carryover import carry_over_subtasks


async def run(only_today: bool) -> None:
    async with async_session() as db:
        query = (
            select(DailyTask)
            .join(DailyPlan, DailyTask.daily_plan_id == DailyPlan.id)
            .options(selectinload(DailyTask.subtasks))
        )
        if only_today:
            query = query.where(DailyPlan.date == date.today())

        result = await db.execute(query)
        tasks = result.scalars().all()

        total = 0
        touched = 0
        for dt in tasks:
            if dt.subtasks:
                continue
            copied = await carry_over_subtasks(db, dt)
            if copied:
                touched += 1
                total += copied
                print(f"  + DailyTask {dt.id} ({dt.title_snapshot}): {copied} subtarea(s)")

        await db.commit()
        scope = "hoy" if only_today else "todos los planes"
        print(f"\nBackfill ({scope}): {touched} DailyTask(s) actualizadas, {total} subtareas copiadas.")


if __name__ == "__main__":
    only_today = "--all" not in sys.argv
    asyncio.run(run(only_today))
