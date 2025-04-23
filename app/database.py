import os
import motor.motor_asyncio
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get MongoDB URL from environment variables
MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE", "deployment_manager")

if not MONGODB_URL:
    logger.error("MONGODB_URL environment variable is not set. Please set it to your MongoDB connection string.")
    raise ValueError("MONGODB_URL environment variable is not set")

# Log the MongoDB connection (without credentials)
connection_parts = MONGODB_URL.split('@')
if len(connection_parts) > 1:
    logger.info(f"Connecting to MongoDB at: {connection_parts[1]}")
else:
    logger.info("Connecting to MongoDB with connection string (credentials hidden)")

try:
    # Create a client instance
    client = motor.motor_asyncio.AsyncIOMotorClient(
        MONGODB_URL,
        serverSelectionTimeoutMS=5000  # 5 second timeout
    )
    
    # Verify the connection
    client.admin.command('ping')
    logger.info("Successfully connected to MongoDB")
    
    # Get database instance
    db = client[DATABASE_NAME]
    
    # Define collections
    user_workspace_collection = db.user_workspaces
    job_collection = db.triggered_jobs
    
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {str(e)}")
    raise