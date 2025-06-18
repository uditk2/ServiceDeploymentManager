#!/bin/bash

# Simple Docker Installation Script
# Installs Docker, Docker Compose, zip and sets up user permissions

set -e  # Exit on any error

echo "=== Docker Installation Script ==="
echo
# Create necessary directories
echo "Creating necessary directories..."
sudo mkdir -p /home/azureuser/service/logs /home/azureuser/ws /home/azureuser/deployments /home/azureuser/assets
sudo chown $USER:$USER /home/azureuser/service/logs /home/azureuser/ws
echo "Directories created: /home/azureuser/service/logs, /home/azureuser/ws"
echo
# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo "ERROR: Don't run this script as root. Run as regular user."
    echo "The script will use sudo when needed."
    exit 1
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "ERROR: Cannot detect Linux distribution"
    exit 1
fi

echo "Detected OS: $OS"
echo

# Update packages and install prerequisites
echo "Updating system packages..."
case $OS in
    ubuntu|debian)
        sudo apt-get update
        sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release zip unzip
        ;;
    centos|rhel)
        sudo yum update -y
        sudo yum install -y curl zip unzip
        ;;
    fedora)
        sudo dnf update -y
        sudo dnf install -y curl zip unzip
        ;;
    *)
        echo "ERROR: Unsupported OS: $OS"
        exit 1
        ;;
esac

# Install Docker (includes Compose plugin since 2022)
echo "Installing Docker with Compose plugin..."
case $OS in
    ubuntu|debian)
        # Add Docker's GPG key
        curl -fsSL https://download.docker.com/linux/$OS/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        
        # Add Docker repository
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/$OS $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        # Install Docker CE with Compose plugin (integrated since 2022)
        sudo apt-get update
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        ;;
    centos|rhel)
        sudo yum install -y yum-utils
        sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        ;;
    fedora)
        sudo dnf install -y dnf-plugins-core
        sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
        sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        ;;
esac

# Start and enable Docker service
echo "Starting Docker service..."
sudo systemctl start docker
sudo systemctl enable docker

# Add current user to docker group
echo "Adding user $USER to docker group..."
sudo usermod -aG docker $USER

# Install standalone docker-compose (fallback for compatibility)
echo "Installing docker-compose standalone for compatibility..."
COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Apply docker group changes immediately
echo "Applying docker group changes..."
newgrp docker << 'DOCKER_GROUP_END'

echo
echo "=== Installation Complete ==="
echo
echo "Docker version: $(docker --version)"
echo "Docker Compose plugin: $(docker compose version 2>/dev/null || echo 'Not available')"
echo "Docker Compose standalone: $(docker-compose --version 2>/dev/null || echo 'Not available')"
echo "Zip installed: $(zip --version | head -1)"
echo

# Test Docker installation
echo "Testing Docker installation..."
if docker run --rm hello-world > /dev/null 2>&1; then
    echo "✅ Docker test successful!"
else
    echo "❌ Docker test failed. You may need to log out and back in."
fi

echo
echo "🎉 Setup complete! Your deployment script should now work perfectly."
echo
echo "Available commands:"
echo "  - docker compose up -d    (recommended v2 syntax)"
echo "  - docker-compose up -d    (v1 compatible)"
echo

DOCKER_GROUP_END

echo "Docker group activated. You can now use Docker commands without sudo!"
echo