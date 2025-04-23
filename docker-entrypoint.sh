#!/bin/bash
set -e

# Create necessary directories if they don't exist
mkdir -p /app/logs
mkdir -p /app/workspaces

setup_docker() {
    DOCKER_SOCKET="/var/run/docker.sock"
    
    if [ -e "$DOCKER_SOCKET" ]; then
        # Try both Linux and macOS methods to get group ID
        DOCKER_GID=$(stat -c '%g' "$DOCKER_SOCKET" 2>/dev/null || \
                     stat -f '%g' "$DOCKER_SOCKET" 2>/dev/null || \
                     ls -n "$DOCKER_SOCKET" | awk '{print $4}' 2>/dev/null || \
                     echo "999")

        # Try to update docker group GID
        if getent group docker >/dev/null 2>&1; then
            groupmod -g "$DOCKER_GID" docker 2>/dev/null || true
        else
            groupadd -g "$DOCKER_GID" docker 2>/dev/null || true
        fi

        # Ensure appuser is in docker group
        usermod -aG docker appuser 2>/dev/null || true
        
        # Set socket permissions
        chmod 666 "$DOCKER_SOCKET" 2>/dev/null || true
    fi
}

# Main execution
if [ "$(id -u)" = "0" ]; then
    setup_docker
    exec gosu appuser "$@"
else
    exec "$@"
fi