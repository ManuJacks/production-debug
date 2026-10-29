#!/usr/bin/env bash
# run-minikube.sh - Build and deploy production-debug locally inside Minikube
set -euo pipefail

IMAGE_NAME="production-debug:local"

echo "=== 1. Pointing Docker CLI to Minikube environment ==="
eval "$(minikube docker-env)"

echo "=== 2. Building container image directly in Minikube's Docker daemon ==="
docker build -t "${IMAGE_NAME}" -f docker/Dockerfile .

echo "=== 3. Deploying debug pod in Minikube ==="
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: minikube-prod-debug
  labels:
    app: production-debug
spec:
  containers:
  - name: debug
    image: ${IMAGE_NAME}
    imagePullPolicy: Never
    stdin: true
    tty: true
    command: ["/bin/bash"]
EOF

echo "=== 4. Waiting for pod readiness ==="
kubectl wait --for=condition=Ready pod/minikube-prod-debug --timeout=60s

echo "=== 5. Attaching to tmux triage session in Minikube ==="
kubectl exec -it minikube-prod-debug -- /usr/local/bin/launch-tmux-triage.sh
