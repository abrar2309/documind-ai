import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.database.session import get_db
from app.models.membership import WorkspaceMembership
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.auth import (
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceMemberCreate,
    WorkspaceMemberRoleUpdate,
    WorkspaceMembershipResponse,
)

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


def make_slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"
    return f"{base}-{uuid.uuid4().hex[:8]}"


async def get_workspace_access(
    workspace_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
):
    workspace = await db.get(Workspace, workspace_id)

    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    membership = await db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == current_user.id,
        )
    )

    if membership is None:
        raise HTTPException(status_code=403, detail="You are not a workspace member")

    return workspace, membership


async def require_manager(
    workspace_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
):
    workspace, membership = await get_workspace_access(
        workspace_id, current_user, db
    )

    if membership.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Workspace owner or admin permission required",
        )

    return workspace, membership


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    payload: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = Workspace(
        name=payload.name.strip(),
        slug=make_slug(payload.name),
        owner_id=current_user.id,
    )
    db.add(workspace)
    await db.flush()

    db.add(
        WorkspaceMembership(
            user_id=current_user.id,
            workspace_id=workspace.id,
            role="owner",
        )
    )

    await db.commit()
    await db.refresh(workspace)
    return workspace


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(Workspace)
        .join(WorkspaceMembership)
        .where(WorkspaceMembership.user_id == current_user.id)
        .order_by(Workspace.created_at.desc())
    )
    return list(result.all())


@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMembershipResponse],
)
async def list_members(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_workspace_access(workspace_id, current_user, db)

    result = await db.scalars(
        select(WorkspaceMembership)
        .where(WorkspaceMembership.workspace_id == workspace_id)
        .order_by(WorkspaceMembership.created_at.asc())
    )
    return list(result.all())


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    workspace_id: uuid.UUID,
    payload: WorkspaceMemberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace, actor_membership = await require_manager(
        workspace_id, current_user, db
    )

    if payload.role == "admin" and actor_membership.role != "owner":
        raise HTTPException(
            status_code=403,
            detail="Only the workspace owner can grant admin access",
        )

    email = str(payload.email).lower().strip()
    target_user = await db.scalar(select(User).where(User.email == email))

    if target_user is None or not target_user.is_active:
        raise HTTPException(status_code=404, detail="Active user not found")

    existing = await db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == target_user.id,
        )
    )

    if existing:
        raise HTTPException(status_code=409, detail="User is already a member")

    membership = WorkspaceMembership(
        user_id=target_user.id,
        workspace_id=workspace.id,
        role=payload.role,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMembershipResponse,
)
async def update_member_role(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: WorkspaceMemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace, actor_membership = await require_manager(
        workspace_id, current_user, db
    )

    target = await db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    )

    if target is None:
        raise HTTPException(status_code=404, detail="Membership not found")

    if user_id == workspace.owner_id:
        raise HTTPException(status_code=400, detail="Workspace owner role cannot be changed")

    if actor_membership.role != "owner":
        if target.role in ("owner", "admin") or payload.role == "admin":
            raise HTTPException(
                status_code=403,
                detail="Admins cannot change owner or admin roles",
            )

    target.role = payload.role
    await db.commit()
    await db.refresh(target)
    return target


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace, actor_membership = await require_manager(
        workspace_id, current_user, db
    )

    if user_id == workspace.owner_id:
        raise HTTPException(status_code=400, detail="Workspace owner cannot be removed")

    target = await db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    )

    if target is None:
        raise HTTPException(status_code=404, detail="Membership not found")

    if actor_membership.role != "owner" and target.role in ("owner", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Admins cannot remove owners or other admins",
        )

    await db.delete(target)
    await db.commit()
    return None
