#!/bin/bash

# Configuration
REMOTE_USER="azureuser"  # Change this to your VM's username
REMOTE_HOST="98.70.36.150"  # Change this to your VM's IP or hostname
REMOTE_PATH="/home/azureuser/ws"  # Change this to your desired remote path
SSH_KEY_PATH="~/.ssh/azurevm.pem"  # Change this to your SSH private key path
ZIP_FILE="app.zip"

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
    # Stop containers. Commenting traefik. We do not need to bring it down.
    #docker compose -f docker-compose-traefik.yml down
    docker compose -f docker-compose-prod.yml down
    
    # Clean up
    docker system prune -f
    # Flush Redis queue
    docker exec $(docker ps -q -f name=redis) redis-cli FLUSHALL
    docker network prune -f
    #Traefik network is already created. we may not need to create it.
    docker network create traefik-public || true
    # Start with logging
    echo "Starting Traefik..."
    docker compose -f docker-compose-traefik.yml up -d
    
    echo "Starting application..."
    # Fix: Remove duplicate compose file reference
    docker compose -f docker-compose-prod.yml up -d --build
    
    # Check status
    docker compose -f docker-compose-prod.yml ps
    docker compose -f docker-compose-prod.yml logs
EOF

# Clean up local zip file
rm $ZIP_FILE

echo "Deployment completed successfully!"