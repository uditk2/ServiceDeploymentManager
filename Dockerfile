# Stage 1: Build stage
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOG_DIR=/app/logs \
    LOG_LEVEL=INFO

WORKDIR /app

# Install docker-cli with all required dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    gosu \
    gpg \
    lsb-release \
    apt-transport-https \
    ca-certificates \
    openssh-client \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

RUN mkdir -p /app/logs && \
    chmod 777 /app/logs

COPY . .


# Create non-root user and docker group
RUN groupadd -g 999 docker && \
    useradd -m appuser && \
    usermod -aG docker appuser && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app

# Copy SSH private key for VM connections
COPY spot_vm_key.pem /app/ssh/spot_vm_key.pem
RUN chmod 600 /app/ssh/spot_vm_key.pem && chown appuser:appuser /app/ssh/spot_vm_key.pem

# Set up SSH configuration for the appuser
RUN mkdir -p /home/appuser/.ssh && \
    echo "Host *" > /home/appuser/.ssh/config && \
    echo "    IdentityFile /app/ssh/spot_vm_key.pem" >> /home/appuser/.ssh/config && \
    echo "    IdentitiesOnly yes" >> /home/appuser/.ssh/config && \
    echo "    StrictHostKeyChecking no" >> /home/appuser/.ssh/config && \
    echo "    UserKnownHostsFile /dev/null" >> /home/appuser/.ssh/config && \
    chmod 600 /home/appuser/.ssh/config && \
    chown -R appuser:appuser /home/appuser/.ssh


USER appuser
RUN git config --global user.email "appbuilder@synergiqai.com" && \
    git config --global user.name "AppBuilder"
USER root
# Copy and set up entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose port
EXPOSE 8005

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
# Command to run the application - disable access logging to stop health check spam
CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8005", "--workers", "4", "--no-access-log"]