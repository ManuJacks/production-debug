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

# Install modern kubectl (pinned v1.31.2 with multi-arch sha256 verification)
ARG KUBECTL_VER="v1.31.2"
RUN set -eux; \
    ARCH=$(dpkg --print-architecture); \
    curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VER}/bin/linux/${ARCH}/kubectl" -o /usr/local/bin/kubectl; \
    curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VER}/bin/linux/${ARCH}/kubectl.sha256" -o /tmp/kubectl.sha256; \
    echo "$(cat /tmp/kubectl.sha256)  /usr/local/bin/kubectl" | sha256sum --check; \
    rm -f /tmp/kubectl.sha256; \
    chmod +x /usr/local/bin/kubectl

# Install Helm
RUN curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install Staff SRE K8s Diagnostic Suite: K9s, Stern, kubectx/kubens, kubectl-neat, kubectl-tree
ARG K9S_VER="v0.32.7"
ARG STERN_VER="1.31.0"
ARG KUBECTX_VER="v0.9.5"
ARG NEAT_VER="v2.0.4"
ARG TREE_VER="v0.4.3"

RUN set -eux; \
    ARCH=$(dpkg --print-architecture); \
    case "$ARCH" in \
      amd64) KUBECTX_ARCH="x86_64";; \
      arm64) KUBECTX_ARCH="arm64";; \
      *) KUBECTX_ARCH="$ARCH";; \
    esac; \
    # 1. K9s
    curl -fsSL "https://github.com/derailed/k9s/releases/download/${K9S_VER}/k9s_Linux_${ARCH}.tar.gz" | tar -xz -C /usr/local/bin k9s; \
    chmod +x /usr/local/bin/k9s; \
    # 2. Stern
    curl -fsSL "https://github.com/stern/stern/releases/download/v${STERN_VER}/stern_${STERN_VER}_linux_${ARCH}.tar.gz" | tar -xz -C /usr/local/bin stern; \
    chmod +x /usr/local/bin/stern; \
    # 3. kubectx & kubens
    curl -fsSL "https://github.com/ahmetb/kubectx/releases/download/${KUBECTX_VER}/kubectx_${KUBECTX_VER}_linux_${KUBECTX_ARCH}.tar.gz" | tar -xz -C /usr/local/bin kubectx; \
    curl -fsSL "https://github.com/ahmetb/kubectx/releases/download/${KUBECTX_VER}/kubens_${KUBECTX_VER}_linux_${KUBECTX_ARCH}.tar.gz" | tar -xz -C /usr/local/bin kubens; \
    chmod +x /usr/local/bin/kubectx /usr/local/bin/kubens; \
    # 4. kubectl-neat
    curl -fsSL "https://github.com/itaysk/kubectl-neat/releases/download/${NEAT_VER}/kubectl-neat_linux_${ARCH}.tar.gz" | tar -xz -C /usr/local/bin kubectl-neat; \
    chmod +x /usr/local/bin/kubectl-neat; \
    # 5. kubectl-tree
    curl -fsSL "https://github.com/ahmetb/kubectl-tree/releases/download/${TREE_VER}/kubectl-tree_${TREE_VER}_linux_${ARCH}.tar.gz" | tar -xz -C /usr/local/bin kubectl-tree; \
    chmod +x /usr/local/bin/kubectl-tree

# Install Azure CLI
RUN mkdir -p /etc/apt/keyrings && \
    curl -sLS https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg && \
    chmod go+r /etc/apt/keyrings/microsoft.gpg && \
    AZ_DIST=$(lsb_release -cs) && \
    ARCH=$(dpkg --print-architecture) && \
    echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/azure-cli/ ${AZ_DIST} main" > /etc/apt/sources.list.d/azure-cli.list && \
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
