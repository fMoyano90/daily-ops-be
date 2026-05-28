from datetime import datetime, date, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.database import get_db
from app.dependencies import get_current_user
from app.models.goal import Goal, GoalStep, GoalComment, GoalHorizon, GoalStatus, GoalStepStatus
from app.models.user import User
from app.models.project import Project
from app.models.task import Task
from app.schemas.goal import (
    GoalCreate, GoalUpdate, GoalResponse,
    GoalStepCreate, GoalStepUpdate, GoalStepResponse,
    GoalCommentCreate, GoalCommentUpdate, GoalCommentResponse,
    GoalSummaryResponse, GoalSummaryItem,
)

router = APIRouter(prefix="/api/v1/goals", tags=["goals"])


def _to_response(goal: Goal) -> GoalResponse:
    linked_task_ids = [s.linked_task_id for s in goal.steps if s.linked_task_id]
    return GoalResponse(
        **{c: getattr(goal, c) for c in GoalResponse.model_fields.keys() if c not in ("steps", "comments", "linked_task_ids")},
        steps=[GoalStepResponse.model_validate(s) for s in goal.steps],
        comments=[GoalCommentResponse.model_validate(c) for c in goal.comments],
        linked_task_ids=[uid for uid in linked_task_ids if uid is not None],
    )


async def _get_goal_or_404(db: AsyncSession, user: User, goal_id: UUID) -> Goal:
    result = await db.execute(
        select(Goal)
        .where(Goal.id == goal_id, Goal.user_id == user.id)
        .options(selectinload(Goal.steps), selectinload(Goal.comments))
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


def _recalculate_progress(steps: list[GoalStep]) -> float:
    if not steps:
        return 0.0
    completed = sum(1 for s in steps if s.status == GoalStepStatus.completed)
    return round((completed / len(steps)) * 100, 1)


@router.get("", response_model=list[GoalResponse])
async def list_goals(
    horizon: GoalHorizon | None = Query(None),
    status_filter: GoalStatus | None = Query(None, alias="status"),
    project_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Goal).where(Goal.user_id == user.id).options(selectinload(Goal.steps), selectinload(Goal.comments)).order_by(Goal.created_at.desc())
    if horizon:
        query = query.where(Goal.horizon == horizon)
    if status_filter:
        query = query.where(Goal.status == status_filter)
    if project_id:
        query = query.where(Goal.project_id == project_id)
    result = await db.execute(query)
    goals = result.scalars().all()
    return [_to_response(g) for g in goals]


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    data: GoalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project_result = await db.execute(select(Project).where(Project.id == data.project_id, Project.user_id == user.id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    goal = Goal(
        user_id=user.id,
        project_id=data.project_id,
        title=data.title,
        description=data.description,
        horizon=data.horizon,
        start_date=data.start_date,
        target_date=data.target_date,
        anti_goals=data.anti_goals,
        key_results=data.key_results,
    )
    db.add(goal)
    await db.flush()
    result = await db.execute(
        select(Goal)
        .where(Goal.id == goal.id)
        .options(selectinload(Goal.steps), selectinload(Goal.comments))
    )
    goal = result.scalar_one()
    return _to_response(goal)


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    goal = await _get_goal_or_404(db, user, goal_id)
    return _to_response(goal)


@router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: UUID,
    data: GoalUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    goal = await _get_goal_or_404(db, user, goal_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(goal, key, value)
    await db.flush()
    result = await db.execute(
        select(Goal)
        .where(Goal.id == goal.id)
        .options(selectinload(Goal.steps), selectinload(Goal.comments))
    )
    goal = result.scalar_one()
    return _to_response(goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    goal = await _get_goal_or_404(db, user, goal_id)
    await db.delete(goal)
    await db.flush()


@router.post("/{goal_id}/complete", response_model=GoalResponse)
async def complete_goal(
    goal_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    goal = await _get_goal_or_404(db, user, goal_id)
    goal.status = GoalStatus.achieved
    goal.completed_at = datetime.now(timezone.utc)
    goal.progress = 100.0
    await db.flush()
    result = await db.execute(
        select(Goal)
        .where(Goal.id == goal.id)
        .options(selectinload(Goal.steps), selectinload(Goal.comments))
    )
    goal = result.scalar_one()
    return _to_response(goal)


@router.post("/{goal_id}/reopen", response_model=GoalResponse)
async def reopen_goal(
    goal_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    goal = await _get_goal_or_404(db, user, goal_id)
    goal.status = GoalStatus.active
    goal.completed_at = None
    await db.flush()
    result = await db.execute(
        select(Goal)
        .where(Goal.id == goal.id)
        .options(selectinload(Goal.steps), selectinload(Goal.comments))
    )
    goal = result.scalar_one()
    return _to_response(goal)


@router.get("/summary", response_model=GoalSummaryResponse)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Goal).where(Goal.user_id == user.id, Goal.status == GoalStatus.active))
    goals = result.scalars().all()

    def build_item(horizon: GoalHorizon) -> GoalSummaryItem:
        horizon_goals = [g for g in goals if g.horizon == horizon]
        if not horizon_goals:
            return GoalSummaryItem(count=0, avg_progress=0.0)
        avg = sum(g.progress for g in horizon_goals) / len(horizon_goals)
        nearest = min(horizon_goals, key=lambda g: g.target_date)
        return GoalSummaryItem(
            count=len(horizon_goals),
            avg_progress=round(avg, 1),
            nearest_deadline=nearest.target_date.isoformat() if nearest.target_date else None,
            nearest_goal_title=nearest.title,
        )

    return GoalSummaryResponse(
        short=build_item(GoalHorizon.short),
        medium=build_item(GoalHorizon.medium),
        long=build_item(GoalHorizon.long),
    )


# --- Steps ---

@router.get("/{goal_id}/steps", response_model=list[GoalStepResponse])
async def list_steps(
    goal_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_goal_or_404(db, user, goal_id)
    result = await db.execute(select(GoalStep).where(GoalStep.goal_id == goal_id).order_by(GoalStep.sort_order))
    return result.scalars().all()


@router.post("/{goal_id}/steps", response_model=GoalStepResponse, status_code=status.HTTP_201_CREATED)
async def create_step(
    goal_id: UUID,
    data: GoalStepCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_goal_or_404(db, user, goal_id)

    if data.linked_task_id:
        task_result = await db.execute(select(Task).where(Task.id == data.linked_task_id, Task.user_id == user.id))
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

    step = GoalStep(
        goal_id=goal_id,
        title=data.title,
        sort_order=data.sort_order,
        linked_task_id=data.linked_task_id,
        due_date=data.due_date,
    )
    db.add(step)
    await db.flush()
    await db.refresh(step)
    return step


@router.patch("/{goal_id}/steps/{step_id}", response_model=GoalStepResponse)
async def update_step(
    goal_id: UUID,
    step_id: UUID,
    data: GoalStepUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_goal_or_404(db, user, goal_id)
    result = await db.execute(select(GoalStep).where(GoalStep.id == step_id, GoalStep.goal_id == goal_id))
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(step, key, value)

    await db.flush()
    await db.refresh(step)
    return step


@router.delete("/{goal_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_step(
    goal_id: UUID,
    step_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_goal_or_404(db, user, goal_id)
    result = await db.execute(select(GoalStep).where(GoalStep.id == step_id, GoalStep.goal_id == goal_id))
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    await db.delete(step)
    await db.flush()


@router.post("/{goal_id}/steps/{step_id}/complete", response_model=GoalStepResponse)
async def complete_step(
    goal_id: UUID,
    step_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_goal_or_404(db, user, goal_id)
    result = await db.execute(select(GoalStep).where(GoalStep.id == step_id, GoalStep.goal_id == goal_id))
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    if step.status == GoalStepStatus.completed:
        step.status = GoalStepStatus.pending
        step.completed_at = None
    else:
        step.status = GoalStepStatus.completed
        step.completed_at = datetime.now(timezone.utc)

    all_result = await db.execute(select(GoalStep).where(GoalStep.goal_id == goal_id))
    all_steps = all_result.scalars().all()
    goal = await db.get(Goal, goal_id)
    goal.progress = _recalculate_progress(all_steps)

    await db.flush()
    await db.refresh(step)
    return step


@router.put("/{goal_id}/steps/reorder", response_model=dict)
async def reorder_steps(
    goal_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_goal_or_404(db, user, goal_id)
    step_ids = data.get("step_ids", [])
    updated = 0
    for idx, step_id_str in enumerate(step_ids):
        step_id = UUID(step_id_str) if isinstance(step_id_str, str) else step_id_str
        result = await db.execute(select(GoalStep).where(GoalStep.id == step_id, GoalStep.goal_id == goal_id))
        step = result.scalar_one_or_none()
        if step:
            step.sort_order = idx
            updated += 1
    await db.flush()
    return {"updated_count": updated}


# --- Comments ---

@router.get("/{goal_id}/comments", response_model=list[GoalCommentResponse])
async def list_comments(
    goal_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_goal_or_404(db, user, goal_id)
    result = await db.execute(select(GoalComment).where(GoalComment.goal_id == goal_id).order_by(GoalComment.created_at.desc()))
    return result.scalars().all()


@router.post("/{goal_id}/comments", response_model=GoalCommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    goal_id: UUID,
    data: GoalCommentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_goal_or_404(db, user, goal_id)
    comment = GoalComment(goal_id=goal_id, user_id=user.id, content=data.content)
    db.add(comment)
    await db.flush()
    await db.refresh(comment)
    return comment


@router.patch("/goal-comments/{comment_id}", response_model=GoalCommentResponse)
async def update_comment(
    comment_id: UUID,
    data: GoalCommentUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    comment = await db.get(GoalComment, comment_id)
    if not comment or comment.user_id != user.id:
        raise HTTPException(status_code=404, detail="Comment not found")
    comment.content = data.content
    await db.flush()
    await db.refresh(comment)
    return comment


@router.delete("/goal-comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    comment = await db.get(GoalComment, comment_id)
    if not comment or comment.user_id != user.id:
        raise HTTPException(status_code=404, detail="Comment not found")
    await db.delete(comment)
    await db.flush()
