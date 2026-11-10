# =============================================================================
# Stage 1 — builder
# Compiles all Perl XS modules, builds Python venvs, and downloads all static
# Go binaries.  Nothing from this stage's build toolchain reaches the final image.
# =============================================================================
FROM debian:bookworm-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive

# Build toolchain + runtime Perl interpreter + Python venv support
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    perl \
    cpanminus \
    gcc \
    make \
    libssl-dev \
    libpcap-dev \
    libreadline-dev \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Binary versions (pinned — override at build time with --build-arg if needed)
# ---------------------------------------------------------------------------
ARG KUBECTL_VER="v1.31.2"
ARG HELM_VER="v3.17.3"
ARG K9S_VER="v0.32.7"
ARG STERN_VER="1.31.0"
ARG KUBECTX_VER="v0.9.5"
ARG NEAT_VER="v2.0.4"
ARG TREE_VER="v0.4.3"
ARG CRICTL_VER="v1.31.1"
ARG ETCD_VER="v3.7.3"
ARG GRPCURL_VER="v1.9.1"
ARG CURLIE_VER="v1.7.2"

# Download all static Go/release binaries into /opt/bins
# Verified where upstream provides checksums; extracted directly to avoid
# leaving tarballs in the builder layer.
RUN set -eux; \
    ARCH=$(dpkg --print-architecture); \
    mkdir -p /opt/bins; \
    \
    # 1. kubectl (sha256-verified)
    curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VER}/bin/linux/${ARCH}/kubectl" \
      -o /opt/bins/kubectl; \
    curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VER}/bin/linux/${ARCH}/kubectl.sha256" \
      -o /tmp/kubectl.sha256; \
    echo "$(cat /tmp/kubectl.sha256)  /opt/bins/kubectl" | sha256sum --check; \
    rm -f /tmp/kubectl.sha256; \
    \
    # 2. Helm (sha256-verified)
    HELM_FILE="helm-${HELM_VER}-linux-${ARCH}.tar.gz"; \
    curl -fsSL "https://get.helm.sh/${HELM_FILE}" -o "/tmp/${HELM_FILE}"; \
    curl -fsSL "https://get.helm.sh/${HELM_FILE}.sha256sum" -o /tmp/helm.sha256sum; \
    echo "$(awk '{print $1}' /tmp/helm.sha256sum)  /tmp/${HELM_FILE}" | sha256sum --check; \
    tar -xz --strip-components=1 -C /opt/bins -f "/tmp/${HELM_FILE}" "linux-${ARCH}/helm"; \
    rm -f "/tmp/${HELM_FILE}" /tmp/helm.sha256sum; \
    \
    # 3. K9s
    curl -fsSL "https://github.com/derailed/k9s/releases/download/${K9S_VER}/k9s_Linux_${ARCH}.tar.gz" \
      | tar -xz -C /opt/bins k9s; \
    \
    # 4. Stern
    curl -fsSL "https://github.com/stern/stern/releases/download/v${STERN_VER}/stern_${STERN_VER}_linux_${ARCH}.tar.gz" \
      | tar -xz -C /opt/bins stern; \
    \
    # 5. kubectx & kubens (upstream tarballs use x86_64 not amd64)
    case "$ARCH" in \
      amd64) KUBECTX_ARCH="x86_64";; \
      arm64) KUBECTX_ARCH="arm64";; \
      *) KUBECTX_ARCH="$ARCH";; \
    esac; \
    curl -fsSL "https://github.com/ahmetb/kubectx/releases/download/${KUBECTX_VER}/kubectx_${KUBECTX_VER}_linux_${KUBECTX_ARCH}.tar.gz" \
      | tar -xz -C /opt/bins kubectx; \
    curl -fsSL "https://github.com/ahmetb/kubectx/releases/download/${KUBECTX_VER}/kubens_${KUBECTX_VER}_linux_${KUBECTX_ARCH}.tar.gz" \
      | tar -xz -C /opt/bins kubens; \
    \
    # 6. kubectl-neat
    curl -fsSL "https://github.com/itaysk/kubectl-neat/releases/download/${NEAT_VER}/kubectl-neat_linux_${ARCH}.tar.gz" \
      | tar -xz -C /opt/bins kubectl-neat; \
    \
    # 7. kubectl-tree
    curl -fsSL "https://github.com/ahmetb/kubectl-tree/releases/download/${TREE_VER}/kubectl-tree_${TREE_VER}_linux_${ARCH}.tar.gz" \
      | tar -xz -C /opt/bins kubectl-tree; \
    \
    # 8. crictl
    curl -fsSL "https://github.com/kubernetes-sigs/cri-tools/releases/download/${CRICTL_VER}/crictl-${CRICTL_VER}-linux-${ARCH}.tar.gz" \
      | tar -xz -C /opt/bins crictl; \
    \
    # 9. etcdctl + etcdutl (server binary intentionally excluded)
    case "$ARCH" in \
      amd64) ETCD_ARCH="amd64";; \
      arm64) ETCD_ARCH="arm64";; \
      *) echo "Unsupported arch: $ARCH" && exit 1;; \
    esac; \
    curl -fsSL "https://github.com/etcd-io/etcd/releases/download/${ETCD_VER}/etcd-${ETCD_VER}-linux-${ETCD_ARCH}.tar.gz" \
      -o /tmp/etcd.tar.gz; \
    tar -xz --strip-components=1 -C /opt/bins -f /tmp/etcd.tar.gz \
      "etcd-${ETCD_VER}-linux-${ETCD_ARCH}/etcdctl" \
      "etcd-${ETCD_VER}-linux-${ETCD_ARCH}/etcdutl"; \
    rm -f /tmp/etcd.tar.gz; \
    \
    # 10. grpcurl
    curl -fsSL "https://github.com/fullstorydev/grpcurl/releases/download/${GRPCURL_VER}/grpcurl_${GRPCURL_VER#v}_linux_${ARCH}.tar.gz" \
      | tar -xz -C /opt/bins grpcurl; \
    \
    # 11. curlie
    case "$ARCH" in \
      amd64) CURLIE_ARCH="amd64";; \
      arm64) CURLIE_ARCH="arm64";; \
      *) echo "Unsupported arch: $ARCH" && exit 1;; \
    esac; \
    curl -fsSL "https://github.com/rs/curlie/releases/download/${CURLIE_VER}/curlie_${CURLIE_VER#v}_linux_${CURLIE_ARCH}.tar.gz" \
      | tar -xz -C /opt/bins curlie; \
    \
    chmod +x /opt/bins/*

# ---------------------------------------------------------------------------
# Compile Perl CPAN XS modules into an isolated vendor prefix.
# cpanm -l /opt/perl-vendor installs into:
#   /opt/perl-vendor/lib/perl5/           (pure-Perl modules)
#   /opt/perl-vendor/lib/perl5/<archname> (compiled XS .so files)
# gcc + libssl-dev + libpcap-dev + libreadline-dev are required here
# but will NOT be present in the final image.
# ---------------------------------------------------------------------------
RUN cpanm --notest --quiet -l /opt/perl-vendor \
    JSON::XS \
    LWP::UserAgent \
    LWP::Protocol::https \
    Net::DNS \
    Net::Ping \
    IO::Socket::SSL \
    Net::SNMP \
    Net::Pcap \
    Net::Whois::Raw \
    Term::ReadLine::Gnu \
    && rm -rf ~/.cpanm/work/* \
    # Record the arch-specific lib dir so the final stage can set PERL5LIB correctly
    && perl -MConfig -e \
       'print "/opt/perl-vendor/lib/perl5:/opt/perl-vendor/lib/perl5/$Config{archname}\n"' \
       > /opt/perl-vendor/.perl5lib

# ---------------------------------------------------------------------------
# Build Python venvs from requirements files.
# The complete, self-contained venvs are copied to the final image — no pip
# or compiler needed there.
# ---------------------------------------------------------------------------
COPY mcp/requirements.txt /tmp/mcp-requirements.txt
COPY mcp/requirements-nettools.txt /tmp/requirements-nettools.txt

RUN python3 -m venv /opt/mcp-venv && \
    /opt/mcp-venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/mcp-venv/bin/pip install --no-cache-dir -r /tmp/mcp-requirements.txt

RUN python3 -m venv /opt/nettools-venv && \
    /opt/nettools-venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/nettools-venv/bin/pip install --no-cache-dir -r /tmp/requirements-nettools.txt


# =============================================================================
# Stage 2 — final image
# Runtime-only packages.  No compiler, no -dev headers, no build tools.
# gcc, make, libssl-dev, libpcap-dev, libreadline-dev are absent here.
# =============================================================================
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

# Runtime apt packages — no build toolchain
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core utilities
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
    # DNS & network diagnostics
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
    # System observation
    htop \
    strace \
    lsof \
    tree \
    vim \
    bsdextrautils \
    # Python interpreter (runs pre-built venvs copied from builder)
    python3 \
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
    # Perl interpreter (no compiler — XS modules pre-compiled in builder)
    perl \
    perl-doc \
    # Shared runtime libs required by compiled CPAN XS modules:
    #   Net::Pcap → libpcap0.8
    #   IO::Socket::SSL / LWP::Protocol::https → libssl3 (already pulled by openssl)
    #   Term::ReadLine::Gnu → libreadline8
    libpcap0.8 \
    libreadline8 \
    && rm -rf /var/lib/apt/lists/*

# Install Azure CLI (apt-based Microsoft repo — no compilation needed)
RUN mkdir -p /etc/apt/keyrings && \
    curl -sLS https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg && \
    chmod go+r /etc/apt/keyrings/microsoft.gpg && \
    AZ_DIST=$(lsb_release -cs) && \
    ARCH=$(dpkg --print-architecture) && \
    echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/azure-cli/ ${AZ_DIST} main" > /etc/apt/sources.list.d/azure-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends azure-cli && \
    rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Import artifacts from builder — compiler never touches this stage
# ---------------------------------------------------------------------------

# Pre-verified static binaries → system PATH
COPY --from=builder /opt/bins/ /usr/local/bin/

# Pre-compiled Perl vendor library (pure-Perl + XS .so files)
COPY --from=builder /opt/perl-vendor /opt/perl-vendor

# Set PERL5LIB using the arch-specific path recorded by the builder.
# /etc/profile.d/ covers login shells; ENV covers non-interactive exec.
ENV PERL5LIB=/opt/perl-vendor/lib/perl5
RUN PERL5LIB_FULL=$(cat /opt/perl-vendor/.perl5lib | tr -d '\n') && \
    printf 'export PERL5LIB=%s\n' "${PERL5LIB_FULL}" > /etc/profile.d/perl-vendor.sh && \
    printf 'PERL5LIB=%s\n' "${PERL5LIB_FULL}" >> /etc/environment

# Pre-built Python venvs (all native extensions already compiled in builder)
COPY --from=builder /opt/mcp-venv /opt/mcp-venv
COPY --from=builder /opt/nettools-venv /opt/nettools-venv
ENV PATH="/opt/nettools-venv/bin:$PATH"

# ---------------------------------------------------------------------------
# Non-root debug user — must exist before vim installer writes ~/.vimrc
# ---------------------------------------------------------------------------
RUN useradd -u 10001 -m -s /bin/bash debuguser && \
    mkdir -p /tmp/incident-bundle && \
    chown -R debuguser:debuguser /tmp/incident-bundle

# ---------------------------------------------------------------------------
# vim: amix/vimrc awesome-vimrc runtime + copilot.vim + copilot-chat.vim
# install_awesome_parameterized.sh writes /home/debuguser/.vimrc at build time.
# copilot-language-server intentionally excluded (no Node); plugin loads
# silently — auth mountable later via volume.
# ---------------------------------------------------------------------------
COPY --chown=10001:10001 docker/vim_runtime/ /opt/vim_runtime/
COPY --chown=10001:10001 docker/vim_pack/ /home/debuguser/.vim/pack/
RUN bash /opt/vim_runtime/install_awesome_parameterized.sh /opt/vim_runtime debuguser && \
    chmod -R go-w /opt/vim_runtime /home/debuguser/.vim/pack/

# ---------------------------------------------------------------------------
# MCP server application
# ---------------------------------------------------------------------------
WORKDIR /app
COPY mcp/ /app/mcp/
RUN chown -R debuguser:debuguser /app

# Bundled incident diagnostic scripts
COPY scripts/ /usr/local/bin/
RUN chmod +x /usr/local/bin/*.sh && \
    ln -s /usr/local/bin/launch-tmux-triage.sh /usr/local/bin/k8s-debug-tmux

# Container entrypoint
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER 10001
WORKDIR /home/debuguser

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]
