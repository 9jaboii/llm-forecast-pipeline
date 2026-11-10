# Local Kubernetes runbook

Free, disposable environment for developing and testing the Helm chart,
Argo CD GitOps loop, NetworkPolicies, and Pod Security — before any of it
touches AWS. See `docs/adr/0002-burst-mode-eks-cost.md` for why this exists
as a separate environment instead of iterating directly against EKS.

## What this is

A `kind` (Kubernetes-in-Docker) cluster: one control-plane node, one worker.
`kind`'s default CNI is `kindnet`, which — this is worth knowing, not just
assuming — **does not enforce `NetworkPolicy` resources**. The
`forecaster-default-deny-egress` policy in the Helm chart will apply
without error on this cluster but will not actually restrict traffic here;
it does enforce for real once this chart runs on EKS (whose VPC CNI does
support `NetworkPolicy`). If you want policy enforcement locally too,
install a policy-capable CNI (e.g. Cilium) in place of `kindnet` — not done
by default here, to keep the local loop simple and fast.

## Bring it up

```bash
make kind-up
```

This creates the cluster, applies the namespace (restricted Pod Security
Standard) and a dev-only Postgres (`deploy/kind/postgres.yaml` — never used
outside this cluster; AWS uses RDS instead), builds the Docker image,
loads it directly into the cluster's nodes (no registry needed locally),
and installs the Helm chart with its defaults (`FC_LLM_PROVIDER=fake`, so
no API key or network access is required to see the whole stack running).

## Verify it

```bash
kubectl -n forecaster get pods,cronjobs
kubectl -n forecaster get application 2>/dev/null  # if Argo CD is installed, see below
kubectl -n forecaster port-forward svc/forecaster-api 8000:80
curl -s localhost:8000/healthz
```

Trigger the daily job by hand instead of waiting for its schedule:

```bash
kubectl -n forecaster create job first-run --from=cronjob/forecaster-daily
kubectl -n forecaster logs -f job/first-run
```

Check the egress NetworkPolicy exists (see the CNI caveat above for whether
it's actually enforced on this cluster):

```bash
kubectl -n forecaster describe networkpolicy forecaster-default-deny-egress
```

## Testing with real data instead of the fake provider

```bash
helm upgrade --install forecaster deploy/helm/forecaster --namespace forecaster \
  --set env.FC_LLM_PROVIDER=anthropic \
  --set llm.anthropicApiKey=$FC_ANTHROPIC_API_KEY \
  --set llm.anthropicModel=claude-haiku-4-5-20251001
```

Never commit a real key in a `--set` you've written to a file — pass it
from your shell environment, as above.

## Argo CD (optional, for exercising the full GitOps loop)

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm install argocd argo/argo-cd --namespace argocd --create-namespace
kubectl -n argocd port-forward svc/argocd-server 8080:443
```

Then point an Argo CD `Application` at this repo's `deploy/helm/forecaster`
path on `main`, the same chart used for the local-only `helm upgrade`
above. This proves the push → Argo sync → rolling update loop before it
ever runs against the AWS sandbox.

## Tear down

```bash
make kind-down
```

Destroys the whole cluster. Nothing here is billed, nothing here is
account-specific — unlike the AWS sandbox burst (guide/runbook:
`docs/runbooks/aws-sandbox-burst.md`), there's no cost or cleanup risk to
leaving this running indefinitely, but tearing it down and rebuilding is
also always exactly one command away if something gets into a bad state.
