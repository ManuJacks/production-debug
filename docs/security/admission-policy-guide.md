# Admission policy guide: `production-debug-access-guard`

A study and operations guide for the ValidatingAdmissionPolicy that guards
production-debug's access ([`k8s/admission-policy.yaml`](../../k8s/admission-policy.yaml)).
Read it once from top to bottom. Use the [drills](#8-rehearsal-drills) to
rehearse until you can rebuild the policy without looking.

Security context: [ADR-SEC-001](ADR-SEC-001-diagnostic-access-model.md),
section 3.4.

---

## 1. The problem it solves

The production-debug identity (`debug-system/prod-debug-sa`) is what an AI
assistant uses to read the cluster. Before this policy, the only limit on
*where* it could be granted access was `scripts/grant-incident-access.sh`.
Anyone with permission to create RoleBindings could skip the script:

```bash
kubectl create rolebinding oops -n payments \
  --clusterrole=prod-debug-reader --serviceaccount=debug-system:prod-debug-sa
```

RBAC would allow that, because the person had permission to create
RoleBindings. Nothing would complain. The policy makes the API server itself
refuse it.

## 2. Mental model: where admission sits

Every write request to the API server passes these stages, in order:

```
kubectl ──► 1 Authentication ──► 2 Authorization ──► 3 Mutating ──► 4 Schema ──► 5 Validating ──► etcd
            "who are you?"       (RBAC)                admission      validation    admission
                                 "may YOU do this      "change the                  "is THIS OBJECT
                                  verb on this          object?"                     acceptable?"
                                  resource?"                                         ▲
                                                                                     │
                                                       production-debug-access-guard runs here
```

**The key distinction:**

| | RBAC (stage 2) | Validating admission (stage 5) |
|---|---|---|
| Question | May *this user* do *this verb* on *this resource type*? | Is *this specific object* acceptable, whoever sends it? |
| Sees the object's content? | No | Yes: `object`, `oldObject`, `namespaceObject` |
| Example | "Alice may create RoleBindings in app-team-a" | "No RoleBinding may give prod-debug-sa the `view` role" |
| Checked by `kubectl auth can-i`? | Yes | **No** |

**Lesson:** `kubectl auth can-i create rolebindings -n payments` can say `yes`
while the actual create is denied by this policy. `can-i` only asks RBAC. To
test admission, send the real request with `--dry-run=server`. It passes
through every stage, including admission, and nothing is stored.

## 3. Anatomy of a ValidatingAdmissionPolicy

Two objects, both cluster-scoped, in API group `admissionregistration.k8s.io/v1`
(GA since Kubernetes 1.30):

| Object | Says |
|---|---|
| `ValidatingAdmissionPolicy` | *What* to check: which requests match, and the rules (CEL expressions) |
| `ValidatingAdmissionPolicyBinding` | *Whether, where and how* to enforce it: which policy, optional scope (`matchResources`), optional parameters, and the action |

**A policy without a binding does nothing.** This is the most common
"why isn't it working?" cause.

### The fields used here

```yaml
spec:
  failurePolicy: Fail          # if an expression ERRORS (not "returns false"): reject
  matchConstraints:            # which requests the policy sees at all
    resourceRules:
      - apiGroups: ["rbac.authorization.k8s.io"]
        apiVersions: ["v1"]
        operations: ["CREATE", "UPDATE"]     # not DELETE: revoking must always work
        resources: ["rolebindings", "clusterrolebindings"]
  variables:                   # named sub-expressions, reused as variables.<name>
    - name: ...
      expression: ...
  validations:                 # each must evaluate to true, or the request is rejected
    - expression: ...          # CEL; true = allowed
      messageExpression: ...   # CEL that builds the error message
      reason: Forbidden        # HTTP reason returned (403)
```

Binding:

```yaml
spec:
  policyName: production-debug-access-guard
  validationActions: [Deny]    # Deny | Warn | Audit (Deny and Warn cannot be combined)
```

### What a CEL expression can see

| Variable | Contents |
|---|---|
| `object` | The incoming object (null on DELETE) |
| `oldObject` | The existing object on UPDATE (null on CREATE) |
| `request` | Admission request: `kind`, `namespace`, `operation`, `userInfo`, … |
| `namespaceObject` | The namespace the object lives in (**null for cluster-scoped objects**) |
| `variables` | Your named `variables` |
| `params` | Parameter resource (if `paramKind` is set; not used here) |
| `authorizer` | Lets an expression make RBAC checks (not used here) |

## 4. Our policy, line by line

### Variables

```cel
debugRoles        = ['prod-debug-reader', 'prod-debug-log-reader', 'prod-debug-cluster-reader']

refsDebugRole     = object.roleRef.kind == 'ClusterRole' &&
                    object.roleRef.name in variables.debugRoles

bindsDebugIdentity = has(object.subjects) && object.subjects.exists(s,
                       (s.kind == 'ServiceAccount' && s.name == 'prod-debug-sa' &&
                          has(s.namespace) && s.namespace == 'debug-system') ||
                       (s.kind == 'User'  && s.name == 'system:serviceaccount:debug-system:prod-debug-sa') ||
                       (s.kind == 'Group' && s.name == 'system:serviceaccounts:debug-system'))

isRoleBinding     = request.kind.kind == 'RoleBinding'

nsApproved        = namespaceObject != null &&
                    has(namespaceObject.metadata.labels) &&
                    'production-debug/diagnosable' in namespaceObject.metadata.labels &&
                    namespaceObject.metadata.labels['production-debug/diagnosable'] == 'true'
```

Points worth knowing:

- **The ServiceAccount has three names.** RBAC subjects can name it as
  `kind: ServiceAccount`, as `kind: User` with the username
  `system:serviceaccount:<ns>:<name>`, or through its namespace group
  `system:serviceaccounts:<ns>`. Checking only the first would leave two
  bypasses.
- **`has()` guards before access.** Reading a missing field is a *runtime
  error*, not `false`. With `failurePolicy: Fail` that rejects the request
  with an unhelpful message. With `Ignore` it would *allow* it. Guard
  optional fields with `has()`. (Every namespace has at least the automatic
  `kubernetes.io/metadata.name` label, so this guard is defensive.)
- **`'key' in map`** tests whether a key exists. **`list.exists(x, cond)`** is
  true if any element matches.
- **`namespaceObject` is null for ClusterRoleBindings.** That's why Rule 1
  only applies when `isRoleBinding`.

### The five rules

CEL has no `if`. "If A then B" is written `!A || B`. Read each rule as
"if this binding is X, then it must satisfy Y".

| Rule | Expression | Read as |
|---|---|---|
| 1 | `!isRoleBinding \|\| !refsDebugRole \|\| (not a system namespace && nsApproved)` | If it is a RoleBinding to a debug role, the namespace must be approved and not a system namespace |
| 2 | `isRoleBinding \|\| !refsDebugRole \|\| roleRef.name == 'prod-debug-cluster-reader'` | If it is a ClusterRoleBinding to a debug role, it must be Layer 1 |
| 3 | `!bindsDebugIdentity \|\| refsDebugRole` | If it names the debug identity, it must reference a debug role |
| 4 | `!isRoleBinding \|\| !refsDebugRole \|\| operation != CREATE \|\| (expiresAt is RFC 3339 UTC && creation < expiresAt <= creation + 24h10m)` | If it is a new grant, it must say when it expires, at most a day ahead |
| 5 | `!isRoleBinding \|\| !refsDebugRole \|\| operation != UPDATE \|\| expiresAt == oldExpiresAt` | If it is an existing grant, its expiry cannot change |

**Rule 1 applies to any subject.** Binding `prod-debug-reader` to *another*
ServiceAccount in an unapproved namespace is also denied. The roles exist
for production-debug, so they follow its rules.

**Rule 3 is the most important one.** Without it, anyone could create a
ClusterRoleBinding of `cluster-admin` to the debug ServiceAccount, and the
read-only design would be gone.

**Rules 4 and 5 make grants temporary.** Admission CEL has no "now", so
Rule 4 measures the expiry against `object.metadata.creationTimestamp`. The
API server sets that before validating admission runs on CREATE (also with
`--dry-run=server`). That gives a cap relative to creation. The 10 minutes
over 24 h absorb clock skew between the operator's machine, which computes
the expiry, and the API server. On UPDATE `creationTimestamp` is old, so the
cap cannot be re-checked. Rule 5 therefore freezes the expiry instead:
extending access means revoke and grant again, and each grant is a separate
audited event. The `prod-debug-grant-reaper` CronJob (`k8s/grant-reaper.yaml`)
deletes grants every 5 minutes once their time has passed. Admission only
gates writes, so something has to remove them.

## 5. Behaviour you must know (and will be asked about)

1. **It only checks new requests.** A binding created before the label was
   removed *keeps working*. Admission is a gate on writes, not a scanner.
   `test-access-guard.sh` case 25 proves this. When you withdraw approval,
   also revoke the bindings.
2. **UPDATE is checked too.** Even a harmless label change on a binding that
   no longer complies is denied (case 26).
3. **DELETE is never matched.** Revoking always works (cases 23 and 27). The
   grant reaper depends on this too. Matching
   DELETE could lock you out of cleaning up.
4. **It takes effect after a few seconds.** The API server loads and compiles
   policies asynchronously. A request sent right after `kubectl apply` may
   still pass. The test script waits for a known-bad request to be denied
   before it starts.
5. **`status.typeChecking` catches some mistakes, not all.** The API server
   type-checks expressions and reports what it finds there:
   ```bash
   kubectl get validatingadmissionpolicy production-debug-access-guard -o jsonpath='{.status}'
   # {"observedGeneration":1,"typeChecking":{}}
   ```
   An empty result is not proof the policy works. In testing on v1.36, a
   misspelt field (`object.roleRef.nam`) left `typeChecking` empty and only
   failed when a request arrived: `composited variable "refsDebugRole" fails
   to evaluate: no such key: nam`. The real proof is to run the test cases.
6. **`failurePolicy` is about errors, not about `false`.** A rule that returns
   `false` always rejects. `failurePolicy` only decides what happens when
   evaluation fails, for example a missing field or a bad parameter.
   Security policies use `Fail`.
7. **A broken `Fail` policy blocks everything it matches.** With the typo
   above, *every* RoleBinding and ClusterRoleBinding create or update in the
   whole cluster was denied, not just production-debug's. Keep
   `matchConstraints` as narrow as possible, test changes with a scratch copy
   or on kind first, and remember that removing the binding
   (`kubectl delete validatingadmissionpolicybinding ...`) disables the
   policy at once.
8. **A cluster-admin can delete the policy.** Admission raises the bar from
   "anyone who can create RoleBindings, possibly by accident" to "a
   cluster-admin, deliberately changing a security control". API audit
   logging should then record that change (ADR-SEC-001 section 7).
9. **Kustomize `namespace:` gotcha.** Kustomize's namespace transformer
   stamps a namespace onto kinds it doesn't know are cluster-scoped,
   including these. The API server ignores it, but it is wrong. Our
   kustomizations therefore set namespaces explicitly per object.
10. **Label values are strings.** `production-debug/diagnosable: "true"` must
   be quoted in YAML. Unquoted `true` is a boolean, and kubectl refuses the
   manifest: `cannot unmarshal bool into Go struct field ObjectMeta.metadata.labels of type string`.

## 6. Testing it

### Automated: 27 live cases

```bash
kubectl apply -k k8s/                                   # or: -f k8s/rbac.yaml -f k8s/admission-policy.yaml
scripts/test-access-guard.sh "$(kubectl config current-context)"
```

The script creates two temporary namespaces, sends every case with
`--dry-run=server`, prints `ok`/`FAIL` per case, and cleans up. CI runs it on
kind for every pull request. Expected output:

```
Rule 1: production-debug roles only in labelled namespaces
 ok    1 allow reader into labelled namespace
 ...
 ok   27 allow deleting it is never blocked

all 27 cases matched
```

### By hand

```bash
# Denied by the policy (note who denied it, and the message):
kubectl create rolebinding x -n kif-drill --clusterrole=prod-debug-reader \
  --serviceaccount=debug-system:prod-debug-sa --dry-run=server
# error: ... is forbidden: ValidatingAdmissionPolicy 'production-debug-access-guard'
#   with binding 'production-debug-access-guard' denied request: production-debug roles
#   may only be bound in namespaces labelled production-debug/diagnosable=true;
#   namespace kif-drill is not approved

# RBAC alone says yes. This is the can-i vs admission gap:
kubectl auth can-i create rolebindings -n kif-drill        # yes
```

**Reading a denial:** `is forbidden: ValidatingAdmissionPolicy '<policy>' with
binding '<binding>' denied request: <message>` means admission refused it. A
plain RBAC refusal looks like `User "x" cannot create resource "rolebindings"`.
The wording tells you which stage said no.

## 7. Debugging: "the policy isn't enforcing"

Work down the list:

1. Does the API support it? `kubectl api-resources | grep validatingadmissionpolic`
2. Does the policy exist? `kubectl get validatingadmissionpolicy`
3. **Does the binding exist, and does it name the policy?**
   `kubectl get validatingadmissionpolicybinding -o yaml`
4. Is `validationActions` `[Deny]`? `[Warn]` only prints a warning, and
   `[Audit]` only writes audit annotations.
5. Is `status.typeChecking` empty? (Necessary, not sufficient: see section 5, item 5.)
6. Does `matchConstraints` match the request? Check the API group, the
   version, the operation, and that the resource is **plural** (`rolebindings`).
7. Did you wait a few seconds after applying?
8. Is the request really going through admission? `--dry-run=client` never
   reaches the server. Use `--dry-run=server`.

## 8. Rehearsal drills

Do these on a disposable cluster (kind) or in throwaway namespaces. Predict
the result **before** running each command. The predictions are the skill.

**D1: Rebuild from memory (target: 15 minutes).**
Delete the policy and binding. Write both again without looking. Pass
`scripts/test-access-guard.sh`. Compare your version with
`k8s/admission-policy.yaml`.

**D2: The can-i gap.**
Show that `kubectl auth can-i create rolebindings -n kif-drill` says `yes`
while the create is denied. Explain in one sentence why.
*Answer: can-i asks only the authorizer (stage 2); the policy is admission
(stage 5).*

**D3: Warn mode.**
Change the binding to `validationActions: [Warn]`. Repeat a denied request.
*Expected: it succeeds, and kubectl prints `Warning: Validation failed for
ValidatingAdmissionPolicy ...`.* Put it back to `[Deny]` and run the test
script.

**D4: Break an expression.**
Change `object.roleRef.name` to `object.roleRef.nam` and apply.
*Expected: `status.typeChecking` may stay empty. Requests then fail with
`fails to evaluate: no such key: nam` and are denied because
`failurePolicy: Fail`. That includes unrelated RoleBindings anywhere in
the cluster: try `kubectl create rolebinding z -n default --clusterrole=view
--user=u --dry-run=server`.* Then predict what `failurePolicy: Ignore` would
do. *Answer: every request is allowed, including the ones the policy exists
to stop. A broken security policy would fail open.* **Do this drill on kind
or with a scratch copy that watches a role name nothing uses, never on the
real policy in a shared cluster.**

**D5: Withdraw approval during an incident.**
`grant app-team-b`. Then `kubectl label ns app-team-b production-debug/diagnosable-`.
Predict:
1. Can the pod still list pods in `app-team-b`?
2. Does `grant app-team-b` work again?
3. Does `revoke app-team-b` work?

*Answers: 1 yes (existing bindings are not re-checked). 2 no (the script
refuses, and the API would deny). 3 yes (DELETE is never matched).*
Re-apply kubernetes-in-finance `kubernetes/tenants` afterwards.

**D6: Find the gap that is deliberately left open.**
Rule 3 does not catch bindings to the groups `system:serviceaccounts` (all
ServiceAccounts) or `system:authenticated` (everyone). Show that
`kubectl create clusterrolebinding x --clusterrole=view --group=system:serviceaccounts --dry-run=server`
is allowed. Then explain why matching those groups is dangerous.
*Answer: the API server reconciles built-in bindings such as
`system:basic-user`, which names `system:authenticated`. A `Fail` policy
that rejected those updates could break control-plane reconciliation. The
risk is accepted and recorded in ADR-SEC-001.*

**D7: Write a different policy from scratch.**
Deny Deployments with more than 3 replicas in namespaces labelled
`kif.io/tenant`. Hints: `object.spec.replicas`, `namespaceObject`, and
`has()` (replicas can be omitted).

## 9. Exam relevance

- **CKA:**
  - the request path (authentication, authorization, admission)
  - RBAC objects and the RoleBinding-to-ClusterRole pattern
  - `kubectl auth can-i` and its subresource trap
  - `--dry-run=server`
  - where the API server's admission configuration lives (`--enable-admission-plugins`
    in `/etc/kubernetes/manifests/kube-apiserver.yaml`)

  ValidatingAdmissionPolicy itself is beyond the core CKA, but the request
  path it sits on is not.
- **CKS:** admission control is central, alongside Pod Security Admission and
  policy engines. This policy is a CKS-level exercise.

## 10. Command reference

```bash
kubectl get validatingadmissionpolicy,validatingadmissionpolicybinding
kubectl get validatingadmissionpolicy production-debug-access-guard -o jsonpath='{.status}'
kubectl explain validatingadmissionpolicy.spec.validations
kubectl get ns -l production-debug/diagnosable=true          # approved namespaces
kubectl label ns <ns> production-debug/diagnosable=true      # platform approval (via kubernetes-in-finance)
scripts/test-access-guard.sh "$(kubectl config current-context)"
```
