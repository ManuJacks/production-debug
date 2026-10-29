FROM debian:bookworm-slim

LABEL maintainer="ManuJacks <https://github.com/ManuJacks/production-debug>" \
      description="Production K8s & Azure Incident Diagnostic Toolkit" \
      security.standards="Staff/Principal SRE - Least-Privilege & Read-Only Diagnostics"

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TERM=xterm-256color \
    INCIDENT_LOG_DIR=/tmp/incident-bundle

# Install base packages, networking, and diagnostic utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    gnupg \
    lsb-release \
    apt-transport-https \
    tmux \
    jq \
    ripgrep \
    bind9-dnsutils \
    iproute2 \
    net-tools \
    tcpdump \
    iperf3 \
    nmap \
    mtr-tiny \
    socat \
    traceroute \
    conntrack \
    openssl \
    htop \
    strace \
    lsof \
    tree \
    vim-tiny \
    bsdextrautils \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Install modern kubectl (latest stable v1.31)
RUN curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.31/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg && \
    echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.31/deb/ /' > /etc/apt/sources.list.d/kubernetes.list && \
    apt-get update && apt-get install -y --no-install-recommends kubectl && \
    rm -rf /var/lib/apt/lists/*

# Install Helm
RUN curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install Azure CLI
RUN mkdir -p /etc/apt/keyrings && \
    curl -sLS https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg && \
    chmod go+r /etc/apt/keyrings/microsoft.gpg && \
    AZ_DIST=$(lsb_release -cs) && \
    echo "deb [arch=amd64,arm64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/azure-cli/ $AZ_DIST main" > /etc/apt/sources.list.d/azure-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends azure-cli && \
    rm -rf /var/lib/apt/lists/*

# Setup application directory & install python dependencies for MCP server
WORKDIR /app
COPY mcp/ /app/mcp/
RUN python3 -m venv /opt/mcp-venv && \
    /opt/mcp-venv/bin/pip install --no-cache-dir -r /app/mcp/requirements.txt || true

# Copy bundled incident diagnostic scripts to system PATH
COPY scripts/ /usr/local/bin/
RUN chmod +x /usr/local/bin/*.sh && \
    ln -s /usr/local/bin/launch-tmux-triage.sh /usr/local/bin/k8s-debug-tmux

# Copy container entrypoint
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Create non-root debug user and workspace directories
RUN useradd -u 10001 -m -s /bin/bash debuguser && \
    mkdir -p /tmp/incident-bundle && \
    chown -R debuguser:debuguser /tmp/incident-bundle /app

USER 10001
WORKDIR /home/debuguser

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]
