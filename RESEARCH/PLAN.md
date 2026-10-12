# Multi-region deployments — implementation plan

## Goal
Build a **public tutorial** that shows how microservices deploy across multiple GCP regions whenever a central `regions.yaml` is updated, and how service pipelines validate target regions against that config.

This repo (`multi-region-deployments`) is the **central platform/config** repo. The companion example service is [`multi-region-microservice-example`](https://github.com/tunnelWithAC/multi-region-microservice-example).

## Non-goals (v1)
- Live GCP deploys, credentials, WIF, or a real GCP project
- Terraform / IaC provisioning when a region is added (document the dependency only; assume regional capacity already exists)
- Automated teardown when a region is removed or demoted (document options only)
- Equal first-class Bitbucket implementation (GitHub Actions is primary; Bitbucket is docs + fetch script)
- Using `tier` / `endpoint_suffix` in pipeline logic (keep as illustrative fields for later)

## Success criteria
- README explains architecture and both required flows with copy-paste snippets
- Reusable **GitHub Action** (owned by this repo) fetches public `regions.yaml`
- Equivalent **Bitbucket shell script** fetches the same config
- This repo hosts an **orchestrator workflow** that, on `regions.yaml` change, fans out to services listed in `services.yaml` via API-triggered pipeline runs
- Example hello-world service pipeline: loads regions, deploys (mock) to **all active regions**, **fails hard** if a requested region is not enabled
- All deploy steps are **mock/dry-run** (e.g. echo/plan), with docs for how real GCP auth would plug in later

---

## Architecture (v1)

```
multi-region-deployments (this repo)
├── config/regions.yaml          # source of truth for active regions
├── config/services.yaml         # registry of microservice repos to fan out to
├── .github/
│   ├── actions/fetch-regions/   # reusable composite action
│   └── workflows/
│       └── region-fanout.yml    # on regions.yaml change → trigger each service
├── scripts/
│   └── fetch-regions.sh         # Bitbucket-friendly fetch script
├── github/                      # copy-paste GitHub snippets / examples
├── bitbucket/                   # Bitbucket docs + pipeline snippets
└── README.md

multi-region-microservice-example
├── app (minimal hello-world)
└── .github/workflows/deploy.yml # fetch regions → matrix all active → mock deploy
                                 # optional region input → validate or fail hard
```

### Flow A — Region added → fan-out deploy
1. PR merges changing `config/regions.yaml` (e.g. new region under `active_regions`).
2. `region-fanout` workflow runs in this repo.
3. Workflow reads `config/services.yaml` and determines target region(s) (see Open decisions for per-new-region vs full list).
4. For each service entry, call GitHub Actions `workflow_dispatch` (API) with the target region(s).
5. Each service pipeline runs mock deploy for that region after validating it is in `regions.yaml`.

### Flow B — Service code change → validate + multi-region deploy
1. Push/PR on the example microservice.
2. Pipeline uses the reusable action to fetch `regions.yaml` from this public repo.
3. Build matrix over **all** `active_regions`.
4. Mock deploy per region.
5. If a region is passed explicitly (dispatch/input) and is **not** in `active_regions`, **fail the job**.

---

## Config contracts

### `config/regions.yaml`
```yaml
active_regions:
  - name: "us-central1"
    tier: "primary"           # illustrative only in v1
    endpoint_suffix: "us"     # illustrative only in v1
  - name: "europe-west1"
    tier: "primary"
    endpoint_suffix: "eu"
  - name: "asia-east1"
    tier: "secondary"
    endpoint_suffix: "ap"
```

- **Public** — unauthenticated fetch is OK (raw URL or checkout of this repo).
- Pipelines treat `name` as the region id for validation and matrix keys.
- `tier` / `endpoint_suffix` are documented as reserved for future routing/DNS behavior.

### `config/services.yaml`
Registry of repos the fan-out orchestrator triggers, e.g.:
```yaml
services:
  - name: multi-region-microservice-example
    repo: tunnelWithAC/multi-region-microservice-example
    workflow: deploy.yml          # workflow file to dispatch
    ref: main                     # optional default ref
```

---

## Deliverables

### 1. This repo — platform pieces
- `config/regions.yaml` — canonical active regions (already seeded)
- `config/services.yaml` — service registry for fan-out
- `.github/actions/fetch-regions` — reusable composite action: fetch + parse regions; outputs JSON list / matrix
- `scripts/fetch-regions.sh` — same behavior for Bitbucket Pipelines
- `.github/workflows/region-fanout.yml` — orchestrator: on push paths `config/regions.yaml`, read services, `workflow_dispatch` each
- `github/` — snippets: consume action, validate region, matrix deploy (mock)
- `bitbucket/` — docs + `bitbucket-pipelines.yml` snippet using `fetch-regions.sh`
- `README.md` — architecture, both flows, copy-paste usage, dry-run vs real GCP notes, region remove options

### 2. Example service repo
- Minimal hello-world app — smallest runnable/mockable service (language TBD; prefer something trivial)
- `.github/workflows/deploy.yml` — `workflow_dispatch` + `push`; fetch regions via action; matrix all active; mock deploy; fail if invalid region input
- README pointer — link back to this tutorial repo

### 3. Documentation (README-centric)
- Architecture diagram (text/mermaid)
- Flow A and Flow B step-by-step with copy-paste YAML
- How to add a service to `services.yaml`
- How to add a region and what the orchestrator does
- Validation failure behavior
- **Infra prerequisite** (document only): networking/runtime/LB must exist before real deploys
- **Region removal** (document only): options such as stop new deploys vs teardown
- **Real GCP later**: where WIF/SA and `gcloud`/Cloud Run would replace mock steps
- Bitbucket equivalent snippets (secondary)

---

## Implementation notes

### Reusable GitHub Action (`fetch-regions`)
- Inputs: e.g. `config-repo`, `config-path`, `ref` (defaults pointing at this repo / `config/regions.yaml` / default branch)
- Steps: checkout or `curl` raw file; parse YAML to JSON array of region names (and full objects if useful)
- Outputs: e.g. `regions-json` suitable for `strategy.matrix`
- Keep composite action simple; avoid Marketplace publishing for v1 (reference via `owner/repo/.github/actions/fetch-regions@ref`)

### Bitbucket script (`scripts/fetch-regions.sh`)
- Fetch public raw `regions.yaml`
- Emit region names for pipe loops or parallel steps
- Document usage in `bitbucket/` — no requirement for a full working Bitbucket repo in v1

### Orchestrator (`region-fanout.yml`)
- Trigger: push to default branch affecting `config/regions.yaml` (and optionally `workflow_dispatch` for manual replay)
- Permissions: token with rights to dispatch workflows on target repos
- For tutorial: document required secret (e.g. `FANOUT_TOKEN`) with minimal scopes; support dry-run mode that only prints which dispatches would fire
- Read `services.yaml`; for each service, dispatch workflow with payload including region list or single new region

### Example service pipeline
- On push: matrix = all regions from fetched config; mock deploy
- On `workflow_dispatch`: accept optional `region` input
  - if set: validate membership in `active_regions` or **fail**
  - if unset: all active regions
- Mock deploy step: log service name, region, image tag / git sha (no cloud calls)

### Mock vs real GCP
- Default: mock
- README section: replace mock step with auth (WIF) + Cloud Run/GKE deploy; still driven by same region matrix and validation

---

## Suggested build order
1. Finalize `regions.yaml` + add `services.yaml`
2. Implement `fetch-regions` action + smoke check
3. Implement `scripts/fetch-regions.sh` + Bitbucket doc snippet
4. Implement `region-fanout.yml` with dry-run default / documented token
5. Scaffold `multi-region-microservice-example` (hello-world + deploy workflow consuming the action)
6. Write root README (architecture + both flows + copy-paste)
7. Fill `github/` and `bitbucket/` example folders
8. Manual walkthrough checklist (add region → see fan-out logs; push service → matrix mock deploys; invalid region → fail)

---

## Open decisions (minor; choose during implementation)
- Fan-out granularity: dispatch **once per service** with full active region list vs **once per new region**
- Hello-world language/runtime for the example repo (e.g. static file server, Go, or Node one-pager)
- Whether fan-out also runs when `services.yaml` changes (recommended: yes)
- Exact token model for cross-repo dispatch in a public tutorial (PAT secret vs GitHub App)

## Out of scope reminders
- No real multi-region traffic management, data replication, or globally distributed databases (see other `RESEARCH/*.md` for background only)
- No automated region teardown
- No Terraform apply in the fan-out path
