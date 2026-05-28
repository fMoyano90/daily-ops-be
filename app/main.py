from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import (
    auth_router,
    projects_router,
    tasks_router,
    daily_plans_router,
    daily_tasks_router,
    subtasks_router,
    timers_router,
    history_router,
    recurring_tasks_router,
    jira_connections_router,
    task_comments_router,
    push_router,
    goals_router,
)

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(daily_plans_router)
app.include_router(daily_tasks_router)
app.include_router(subtasks_router)
app.include_router(timers_router)
app.include_router(history_router)
app.include_router(recurring_tasks_router)
app.include_router(jira_connections_router)
app.include_router(task_comments_router)
app.include_router(push_router)
app.include_router(goals_router)


@app.get("/")
async def root():
    return {"message": "DailyOps API", "version": settings.APP_VERSION}


@app.get("/health")
async def health_check():
    return {"status": "ok"}
