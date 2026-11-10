FROM debian:bookworm-slim

LABEL org.opencontainers.image.title="production-debug" \
      org.opencontainers.image.description="Ephemeral, safe-by-default Kubernetes and Linux triage container for production incident diagnostics." \
      org.opencontainers.image.source="https://github.com/ManuJacks/production-debug" \
      org.opencontainers.image.documentation="https://github.com/ManuJacks/production-debug/blob/main/README.md" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.vendor="ManuJacks" \
      org.opencontainers.image.authors="ManuJacks" \
      maintainer="ManuJacks <https://github.com/ManuJacks/production-debug>" \
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
    less \
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
    vim \
    bsdextrautils \
    python3 \
    python3-pip \
    python3-venv \
    # --- Extended network diagnostics ---
    # Connectivity & port testing
    netcat-openbsd \
    iputils-arping \
    fping \
    ipcalc \
    # Namespace entry (K8s pod netns debugging)
    util-linux \
    # Protocol dissection & stream reassembly
    tshark \
    ngrep \
    tcpflow \
    # TLS/SSL auditing
    sslscan \
    # NIC / driver statistics
    ethtool \
    # Node-level firewall & service-proxy inspection (requires NET_ADMIN at runtime)
    iptables \
    ipvsadm \
    # --- Perl toolchain ---
    perl \
    perl-doc \
    cpanminus \
    # Build deps for XS (C-extension) CPAN modules and Python native extensions
    gcc \
    make \
    libssl-dev \
    libpcap-dev \
    libreadline-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Perl CPAN modules for network monitoring and diagnostics
# cpanm --notest skips upstream test suites to keep image build time reasonable;
# all modules are well-established, widely-used CPAN distributions.
RUN cpanm --notest --quiet \
    # Fast C-backed JSON parser/encoder — parse k8s/API/etcd payloads inline
    JSON::XS \
    # Full-featured HTTP/HTTPS client (LWP + UA + cookies + redirects + auth)
    LWP::UserAgent \
    LWP::Protocol::https \
    # DNS resolver, zone queries, reverse lookups, SRV/MX/NAPTR record iteration
    Net::DNS \
    # ICMP / TCP / UDP host reachability probes
    Net::Ping \
    # TLS/SSL socket layer (required by LWP::Protocol::https & Net::DNS over TLS)
    IO::Socket::SSL \
    # SNMP v1/v2c/v3 — query switches, node exporters, storage controllers
    Net::SNMP \
    # libpcap bindings — programmatic packet capture and BPF filtering
    Net::Pcap \
    # WHOIS client — domain/IP ownership, ASN, route-origin, abuse contact lookups
    Net::Whois::Raw \
    # GNU ReadLine for the interactive Perl debugger (perl -de1)
    Term::ReadLine::Gnu \
    && rm -rf ~/.cpanm/work/*

# Install modern kubectl (pinned v1.31.2 with multi-arch sha256 verification)
ARG KUBECTL_VER="v1.31.2"
RUN set -eux; \
    ARCH=$(dpkg --print-architecture); \
    curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VER}/bin/linux/${ARCH}/kubectl" -o /usr/local/bin/kubectl; \
    curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VER}/bin/linux/${ARCH}/kubectl.sha256" -o /tmp/kubectl.sha256; \
    echo "$(cat /tmp/kubectl.sha256)  /usr/local/bin/kubectl" | sha256sum --check; \
    rm -f /tmp/kubectl.sha256; \
    chmod +x /usr/local/bin/kubectl

# Install Helm (pinned release with SHA-256 verification)
ARG HELM_VER="v3.17.3"
RUN set -eux; \
    ARCH=$(dpkg --print-architecture); \
    HELM_FILE="helm-${HELM_VER}-linux-${ARCH}.tar.gz"; \
    curl -fsSL "https://get.helm.sh/${HELM_FILE}" -o "/tmp/${HELM_FILE}"; \
    curl -fsSL "https://get.helm.sh/${HELM_FILE}.sha256sum" -o /tmp/helm.sha256sum; \
    echo "$(awk '{print $1}' /tmp/helm.sha256sum)  /tmp/${HELM_FILE}" | sha256sum --check; \
    tar -xz --strip-components=1 -C /usr/local/bin -f "/tmp/${HELM_FILE}" "linux-${ARCH}/helm"; \
    rm -f "/tmp/${HELM_FILE}" /tmp/helm.sha256sum

# Install Staff SRE K8s Diagnostic Suite: K9s, Stern, kubectx/kubens, kubectl-neat, kubectl-tree, crictl, etcdctl/etcdutl, grpcurl, curlie
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

# Install crictl (CRI container runtime inspector — matches kubectl minor version)
ARG CRICTL_VER="v1.31.1"
RUN set -eux; \
    ARCH=$(dpkg --print-architecture); \
    curl -fsSL "https://github.com/kubernetes-sigs/cri-tools/releases/download/${CRICTL_VER}/crictl-${CRICTL_VER}-linux-${ARCH}.tar.gz" \
      | tar -xz -C /usr/local/bin crictl; \
    chmod +x /usr/local/bin/crictl

# Install etcd client tools: etcdctl (live cluster queries) + etcdutl (offline snapshot inspection)
# Note: etcd server binary intentionally excluded — this is a client-only install
ARG ETCD_VER="v3.7.3"
RUN set -eux; \
    ARCH=$(dpkg --print-architecture); \
    case "$ARCH" in \
      amd64) ETCD_ARCH="amd64";; \
      arm64) ETCD_ARCH="arm64";; \
      *) echo "Unsupported arch: $ARCH" && exit 1;; \
    esac; \
    curl -fsSL "https://github.com/etcd-io/etcd/releases/download/${ETCD_VER}/etcd-${ETCD_VER}-linux-${ETCD_ARCH}.tar.gz" \
      -o /tmp/etcd.tar.gz; \
    tar -xz --strip-components=1 -C /usr/local/bin \
      -f /tmp/etcd.tar.gz \
      "etcd-${ETCD_VER}-linux-${ETCD_ARCH}/etcdctl" \
      "etcd-${ETCD_VER}-linux-${ETCD_ARCH}/etcdutl"; \
    rm -f /tmp/etcd.tar.gz; \
    chmod +x /usr/local/bin/etcdctl /usr/local/bin/etcdutl

# Install grpcurl (gRPC service inspector) and curlie (human-readable curl)
ARG GRPCURL_VER="v1.9.1"
ARG CURLIE_VER="v1.7.2"
RUN set -eux; \
    ARCH=$(dpkg --print-architecture); \
    # grpcurl
    curl -fsSL "https://github.com/fullstorydev/grpcurl/releases/download/${GRPCURL_VER}/grpcurl_${GRPCURL_VER#v}_linux_${ARCH}.tar.gz" \
      | tar -xz -C /usr/local/bin grpcurl; \
    chmod +x /usr/local/bin/grpcurl; \
    # curlie
    case "$ARCH" in \
      amd64) CURLIE_ARCH="amd64";; \
      arm64) CURLIE_ARCH="arm64";; \
      *) echo "Unsupported arch: $ARCH" && exit 1;; \
    esac; \
    curl -fsSL "https://github.com/rs/curlie/releases/download/${CURLIE_VER}/curlie_${CURLIE_VER#v}_linux_${CURLIE_ARCH}.tar.gz" \
      | tar -xz -C /usr/local/bin curlie; \
    chmod +x /usr/local/bin/curlie

# Install Azure CLI
RUN mkdir -p /etc/apt/keyrings && \
    curl -sLS https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg && \
    chmod go+r /etc/apt/keyrings/microsoft.gpg && \
    AZ_DIST=$(lsb_release -cs) && \
    ARCH=$(dpkg --print-architecture) && \
    echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/azure-cli/ ${AZ_DIST} main" > /etc/apt/sources.list.d/azure-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends azure-cli && \
    rm -rf /var/lib/apt/lists/*

# Install Python network diagnostic tools into a dedicated venv (separate from MCP venv)
# This keeps the MCP server environment lean and dependency-conflict-free.
COPY mcp/requirements-nettools.txt /tmp/requirements-nettools.txt
RUN python3 -m venv /opt/nettools-venv && \
    /opt/nettools-venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/nettools-venv/bin/pip install --no-cache-dir -r /tmp/requirements-nettools.txt && \
    rm -f /tmp/requirements-nettools.txt
ENV PATH="/opt/nettools-venv/bin:$PATH"

# Install vim configuration: amix/vimrc awesome-vimrc runtime + copilot.vim + copilot-chat.vim
# The install_awesome_parameterized.sh script writes the real ~/.vimrc that sources the runtime.
# copilot-language-server is intentionally excluded (no Node in container);
# the plugin loads silently without it — auth can be added later via volume mount.
COPY --chown=10001:10001 docker/vim_runtime/ /opt/vim_runtime/
COPY --chown=10001:10001 docker/vim_pack/ /home/debuguser/.vim/pack/
RUN bash /opt/vim_runtime/install_awesome_parameterized.sh /opt/vim_runtime debuguser && \
    chmod -R go-w /opt/vim_runtime /home/debuguser/.vim/pack/

# Setup application directory & install python dependencies for MCP server
WORKDIR /app
COPY mcp/ /app/mcp/
RUN python3 -m venv /opt/mcp-venv && \
    /opt/mcp-venv/bin/pip install --no-cache-dir -r /app/mcp/requirements.txt

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
