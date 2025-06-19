from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import List, Optional
from dotenv import load_dotenv
import asyncio
import os
from contextlib import asynccontextmanager

# Load environment variables
load_dotenv()

# Import routes
from app.routes import general, docker, workspaces, jobs, logs, stats

# Import models and repositories
from app.models.workspace import UserWorkspace
from app.models.job import TriggeredJob
from app.repositories.workspace_repository import WorkspaceRepository
from app.repositories.job_repository import JobRepository

# Import log watcher manager
from app.workspace_monitoring.log_watcher_manager import log_watcher_manager
from app.custom_logging import logger
from app.auth_middleware import AuthMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting application...")
    await log_watcher_manager.initialize()
    yield
    # Shutdown
    logger.info("Shutting down application...")
    await log_watcher_manager.shutdown()

# Initialize FastAPI app with lifespan events
app = FastAPI(
    title="Deployment Manager API",
    description="API for managing deployments and running Docker commands",
    version="1.0.0",
    lifespan=lifespan
)

# Add authentication middleware
app.add_middleware(AuthMiddleware)

# Include routers from route modules
app.include_router(general.router)
app.include_router(docker.router)
app.include_router(workspaces.router)
app.include_router(jobs.router)
app.include_router(logs.router)
app.include_router(stats.router)
