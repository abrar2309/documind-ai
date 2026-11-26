from fastapi import APIRouter
from app.api.routes import auth, users, workspaces, documents, agent

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(workspaces.router)
api_router.include_router(documents.router)
api_router.include_router(agent.router)
