#!/bin/bash

# Parse command line arguments
MANAGE_TRAEFIK=false
for arg in "$@"; do
    case $arg in
        traefik=true)
            MANAGE_TRAEFIK=true
            shift
            ;;
        *)
            # Unknown option
            ;;
    esac
done

# Configuration
REMOTE_USER="azureuser"  # Change this to your VM's username
REMOTE_HOST="20.244.12.2"  # Change this to your VM's IP or hostname
REMOTE_PATH="/home/azureuser/ws"  # Change this to your desired remote path
ENTRY_PATH="/home/azureuser"  # Change this to your app's entry point path
SSH_KEY_PATH="~/.ssh/azurevm.pem"  # Change this to your SSH private key path
ZIP_FILE="app.zip"
SERVICE_LOGS_PATH="/home/azureuser/logs"  # Change this to your service logs path
# Create zip file excluding unnecessary directories
zip -r $ZIP_FILE . \
    -x "*.git/*" \
    -x "*__pycache__/*" \
    -x "*venv/*" \
    -x "*denv/*" \
    -x "*.pytest_cache/*" \
    -x "data/*" \
    -x "notebooks/*" \
    -x "container/*" \
    -x "*.DS_Store" \
    -x "logs/*" \
    -x "workspace/*" \
    -x "tests/*" \
    -x "vnc/*" \
    -x "sandbox/*" \
    -x "$ZIP_FILE"

# Copy zip file to remote server
scp -i $SSH_KEY_PATH $ZIP_FILE $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH


# SSH into remote server and execute commands

ssh -i $SSH_KEY_PATH $REMOTE_USER@$REMOTE_HOST << EOF
    cd $REMOTE_PATH
    unzip -o app.zip
    rm app.zip
    
    # Stop containers
    if [ "$MANAGE_TRAEFIK" = true ]; then
        echo "Stopping Traefik..."
        docker compose -f docker-compose-traefik.yml down
    fi
    docker compose -f docker-compose-prod.yml down
    
    # Clean up
    docker system prune -f
    # Flush Redis queue
    docker exec \$(docker ps -q -f name=redis) redis-cli FLUSHALL 2>/dev/null || echo "Redis not running or no containers to flush"
    docker network prune -f
    
    # Create Traefik network if managing Traefik
    if [ "$MANAGE_TRAEFIK" = true ]; then
        docker network create traefik-public || true
        echo "Starting Traefik..."
        docker compose -f docker-compose-traefik.yml up -d
    fi
    
    echo "Starting application..."
    docker compose -f docker-compose-prod.yml up -d --build
    
    # Check status
    docker compose -f docker-compose-prod.yml ps
    if [ "$MANAGE_TRAEFIK" = true ]; then
        echo "Traefik status:"
        docker compose -f docker-compose-traefik.yml ps
    fi
    docker compose -f docker-compose-prod.yml logs
EOF

# Clean up local zip file
rm $ZIP_FILE

echo "Deployment completed successfully!"