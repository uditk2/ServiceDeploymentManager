from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import routes
from app.routes import general, docker, workspaces, jobs, logs, stats

# Import models and repositories
from app.models.workspace import UserWorkspace
from app.models.job import TriggeredJob
from app.repositories.workspace_repository import WorkspaceRepository
from app.repositories.job_repository import JobRepository

# Initialize FastAPI app
app = FastAPI(
    title="Deployment Manager API",
    description="API for managing deployments and running Docker commands",
    version="1.0.0"
)

# Include routers from route modules
app.include_router(general.router)
app.include_router(docker.router)
app.include_router(workspaces.router)
app.include_router(jobs.router)
app.include_router(logs.router)
app.include_router(stats.router)
