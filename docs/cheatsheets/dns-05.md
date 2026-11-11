# Kubernetes Troubleshooting Cheatsheet — Exercise 05: DNS

## 1. Scenario

A Pod attempts to resolve:

```text
service-that-does-not-exist.synthetic.invalid
```

The lookup returns:

```text
Server:         10.112.0.10
Address:        10.112.0.10:53

** server can't find service-that-does-not-exist.synthetic.invalid: NXDOMAIN
```

The Pod remains `Running` and `Ready`.

**Root cause:** The requested DNS name does not exist. The DNS resolver is reachable and responds with `NXDOMAIN`.

## 2. Key concepts

| Component              | Purpose                                                   |
| ---------------------- | --------------------------------------------------------- |
| CoreDNS                | Provides DNS resolution inside the Kubernetes cluster     |
| `kube-dns` Service     | Stable ClusterIP used by Pods for DNS queries             |
| EndpointSlice          | Records the backend DNS endpoints                         |
| `NXDOMAIN`             | DNS response indicating the requested name does not exist |
| Pod `/etc/resolv.conf` | Contains the DNS resolver and search configuration        |

Important: The Kubernetes Service is named `kube-dns` even when CoreDNS is the DNS implementation.

## 3. Diagnostic commands

Set the kubeconfig:

```bash
export KUBECONFIG="$HOME/.kube/kubernetes-in-finance.conf"
```

### Inspect the Pod

```bash
kubectl get pod dns-demo -n production-debug-lab -o wide

kubectl describe pod dns-demo -n production-debug-lab

kubectl logs dns-demo -n production-debug-lab
```

### Inspect DNS configuration inside the Pod

```bash
kubectl exec -n production-debug-lab dns-demo -- cat /etc/resolv.conf
```

Look for:

```text
self-contained.nameserver 10.112.0.10
search production-debug-lab.svc.cluster.local svc.cluster.local cluster.local
options ndots:5
```

Actual search domains and options may vary.

### Inspect the DNS Service

```bash
kubectl get svc kube-dns -n kube-system -o wide

kubectl describe svc kube-dns -n kube-system
```

Check:

- ClusterIP
- UDP/TCP port 53
- Service selector

### Inspect DNS EndpointSlices

```bash
kubectl get endpointslices -n kube-system \
  -l kubernetes.io/service-name=kube-dns -o wide
```

Inspect readiness conditions:

```bash
kubectl get endpointslices -n kube-system \
  -l kubernetes.io/service-name=kube-dns \
  -o jsonpath='{range .items[*].endpoints[*]}{.addresses[0]}{" ready="}{.conditions.ready}{"\n"}{end}'
```

### Inspect DNS Pods

```bash
kubectl get pods -n kube-system -o wide | grep -E 'coredns|kube-dns'
```

Inspect logs:

```bash
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=100
```

## 4. Test DNS resolution

Run a lookup from the existing Pod:

```bash
kubectl exec -n production-debug-lab dns-demo -- \
  nslookup kubernetes.default.svc.cluster.local
```

Test the DNS Service itself:

```bash
kubectl exec -n production-debug-lab dns-demo -- \
  nslookup kube-dns.kube-system.svc.cluster.local
```

Test a deliberately nonexistent name:

```bash
kubectl exec -n production-debug-lab dns-demo -- \
  nslookup service-that-does-not-exist.synthetic.invalid
```

Expected result for the nonexistent name:

```text
NXDOMAIN
```

## 5. Interpret DNS errors

| Result                 | Meaning                           | Investigation                                               |
| ---------------------- | --------------------------------- | ----------------------------------------------------------- |
| `NXDOMAIN`             | Name does not exist               | Verify hostname, namespace and Service name                 |
| `SERVFAIL`             | Resolver failed to complete query | Inspect CoreDNS logs and upstream resolution                |
| `connection timed out` | DNS server did not respond        | Check DNS Pods, Service endpoints and network path          |
| `connection refused`   | Connection rejected               | Check resolver availability and port configuration          |
| Successful lookup      | Name resolved                     | Continue troubleshooting at the application layer if needed |

**Critical distinction:** `NXDOMAIN` is not proof of a broken DNS service. It is a valid DNS response.

## 6. Kubernetes Service DNS naming

A typical Service DNS name is:

```text
<service-name>.<namespace>.svc.cluster.local
```

Example:

```text
my-service.production.svc.cluster.local
```

Within the same namespace, a Pod can usually resolve the short name:

```text
my-service
```

From another namespace, use:

```text
my-service.production
```

Fully qualified names avoid ambiguity.

## 7. Troubleshooting sequence

Use this order to avoid unnecessary changes:

1. Confirm the Pod is running.
2. Inspect `/etc/resolv.conf`.
3. Identify the configured DNS resolver.
4. Confirm the `kube-dns` Service ClusterIP.
5. Inspect EndpointSlices and endpoint readiness.
6. Confirm CoreDNS Pods are healthy.
7. Inspect CoreDNS logs if necessary.
8. Test a known-good Kubernetes Service name.
9. Test the application hostname.
10. Determine whether the name should exist.

Do not restart CoreDNS simply because one lookup returns `NXDOMAIN`.

## 8. Exercise 05 findings

| Layer         | Observed result                                |
| ------------- | ---------------------------------------------- |
| Pod           | `dns-demo` Running and Ready                   |
| Pod IP        | `10.244.4.84`                                  |
| Node          | `tf-ha-worker2`                                |
| DNS resolver  | `10.112.0.10`                                  |
| DNS Service   | `kube-dns`                                     |
| Service ports | 53/UDP, 53/TCP, 9153/TCP                       |
| EndpointSlice | Two backend IPs: `10.244.0.26`, `10.244.0.136` |
| DNS response  | `NXDOMAIN`                                     |
| Root cause    | Requested hostname does not exist              |

Note: The EndpointSlice output confirmed two registered endpoints. Their readiness conditions and the final CoreDNS Pod health check should be verified separately before claiming full backend health.

## 9. Interview explanation

**Question:** A Kubernetes Pod cannot resolve a hostname. How do you troubleshoot it?

**Answer:**

"I start by distinguishing a DNS resolution failure from a DNS connectivity failure. I inspect the Pod's `/etc/resolv.conf` to identify its configured resolver, then verify the `kube-dns` Service and its EndpointSlices. I check CoreDNS Pod health and logs, and test resolution of a known-good Kubernetes Service name.

If the resolver responds with `NXDOMAIN`, I verify whether the requested record should exist before changing cluster DNS. A valid negative DNS response is different from a timeout or `SERVFAIL`. I work from the client outward and only change the layer supported by the evidence."

## 10. Staff-level takeaway

**A failed lookup does not automatically mean DNS infrastructure is broken.**

Separate these concerns:

- Client DNS configuration
- DNS Service discovery
- DNS backend availability
- Network connectivity
- Record existence and correctness
- Application-level hostname configuration

Troubleshoot the actual failure domain, not the symptom alone.

