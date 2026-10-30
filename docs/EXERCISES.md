# Kubernetes failure exercises

These exercises are designed for a disposable Minikube, kind, or k3s cluster. Each exercise should produce a timeline, hypothesis log, evidence bundle, recovery verification, and blameless learning note.

1. **CrashLoopBackOff:** remove a required environment variable; identify the exit reason using describe and previous logs.
2. **ImagePullBackOff:** use a nonexistent tag and then an invalid registry credential; distinguish manifest, registry, and authentication failures.
3. **Pending pod:** combine impossible resource requests, a nonmatching node selector, and an untolerated taint; identify the scheduler predicate.
4. **Readiness failure:** point a readiness probe at the wrong path or port; explain why the pod is Running but absent from EndpointSlices.
5. **DNS failure:** use an invalid Service name or broken resolver configuration; distinguish application, CoreDNS, Service, and upstream failures.
6. **NetworkPolicy denial:** apply default-deny ingress/egress, then restore only DNS and required application traffic.
7. **OOMKilled/eviction:** exceed a container memory limit, then compare container OOM with node-pressure eviction and QoS effects.
8. **RBAC Forbidden:** permit pod reads but deny logs and deployments; use `kubectl auth can-i` to grant only the missing permission.

For every exercise, responders must document symptoms, fault domain, commands, expected versus observed output, recovery, and follow-up controls. Do not practice destructive actions on production clusters.
