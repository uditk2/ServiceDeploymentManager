from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def root():
    """Root endpoint that returns a welcome message."""
    return {"message": "Welcome to Deployment Manager API"}

@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}