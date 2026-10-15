# Shared region list for Bitbucket pipelines

## Goal

Microservice repositories on Bitbucket need the **active region list** from this platform repo during deploy, as a **space-separated string**:

```text
us-central1 europe-west1 asia-east1
```

Canonical source:

```text
config/regions.yaml  →  active_regions[].name
```

**Requirements**

- Logic lives in **multi-region-deployments** (not reimplemented per service).
- Public fetch is OK (no token by default).
- Consumer call site should feel like a GitHub Action: pin a ref, one small block, get `REGIONS`.
- Optional single-region mode must **fail hard** if that region is not in `active_regions`.
- Default deploy path: loop **all** active regions (mock/dry-run is fine for the tutorial).

**GitHub parity today**

- Composite action: `.github/actions/fetch-regions`
- Parser: `scripts/parse_regions.py` (JSON / matrix outputs)

Bitbucket has no native composite actions. The options below are ways to get the same central behaviour.

---

## Output contract (all options)

| Name | Example | Use |
|------|---------|-----|
| `REGIONS` | `us-central1 europe-west1 asia-east1` | Primary Bitbucket loop: `for r in $REGIONS` |
| `REGIONS_JSON` | `["us-central1","europe-west1","asia-east1"]` | Structured tooling |
| `REGION_COUNT` | `3` | Guards / logging |

Order should follow `active_regions` in `regions.yaml`.

---

## Option A — Curl + shell entrypoint (`fetch-regions.sh`)

### Summary

Ship `scripts/fetch-regions.sh` in this repo. Microservices download it (and the shared parser) from a **pinned git ref**, run it, and export `REGIONS`.

Closest mental model to:

```text
uses: tunnelWithAC/multi-region-deployments/.github/actions/fetch-regions@v1
```

except the “pin” is a URL path segment / `REF` variable instead of `uses:`.

### What this repo provides

| Path | Role |
|------|------|
| `config/regions.yaml` | Canonical regions |
| `scripts/parse_regions.py` | Single parse/validate implementation |
| `scripts/fetch-regions.sh` | Bitbucket/CLI entrypoint: fetch → parse → export |
| `bitbucket/` docs | Copy-paste snippets |

**URL contract**

```text
https://raw.githubusercontent.com/tunnelWithAC/multi-region-deployments/<REF>/scripts/fetch-regions.sh
https://raw.githubusercontent.com/tunnelWithAC/multi-region-deployments/<REF>/scripts/parse_regions.py
https://raw.githubusercontent.com/tunnelWithAC/multi-region-deployments/<REF>/config/regions.yaml
```

`<REF>` should be an **immutable tag or commit SHA** in production snippets (not a floating branch until `main` is stable).

**Proposed CLI**

```bash
fetch-regions.sh [--ref REF] [--region NAME] [--format space|json|exports]
```

- `--format exports` → `export REGIONS='…'` (for `eval`)
- `--format space` → bare SSV on stdout
- `--region X` → only that region, or exit `2` if not enabled

### Microservice implementation (Bitbucket)

What the **service repo** must add:

1. A `bitbucket-pipelines.yml` step that pins `REF`, curls the script + parser, and evals exports.
2. A deploy loop over `$REGIONS` (mock or real).
3. Optional: repo/workspace variable `MULTI_REGION_REF` / `REGIONS_REF`.
4. Optional custom pipeline for single-region fan-out with `REGION` / `REQUESTED_REGION`.

**Example `bitbucket-pipelines.yml`**

```yaml
image: python:3.12-slim

definitions:
  scripts:
    fetch-regions: &fetch-regions |
      set -euo pipefail
      REF="${MULTI_REGION_REF:-v1.0.0}"
      BASE="https://raw.githubusercontent.com/tunnelWithAC/multi-region-deployments/${REF}"
      curl -fsSL --retry 3 --retry-delay 2 \
        "${BASE}/scripts/fetch-regions.sh" -o /tmp/fetch-regions.sh
      curl -fsSL --retry 3 --retry-delay 2 \
        "${BASE}/scripts/parse_regions.py" -o /tmp/parse_regions.py
      chmod +x /tmp/fetch-regions.sh
      # Optional hardening:
      # echo "${FETCH_REGIONS_SHA256}  /tmp/fetch-regions.sh" | sha256sum -c -
      eval "$(PARSE_REGIONS_PY=/tmp/parse_regions.py /tmp/fetch-regions.sh --ref "$REF" --format exports ${REGION:+--region "$REGION"})"
      echo "REGIONS=${REGIONS}"
      printf '%s' "${REGIONS}" > regions.ssv

pipelines:
  default:
    - step:
        name: Mock deploy all active regions
        script:
          - *fetch-regions
          - |
            for r in $REGIONS; do
              echo "mock deploy service=${BITBUCKET_REPO_SLUG} region=${r} sha=${BITBUCKET_COMMIT}"
              # Real deploy later, e.g.:
              # gcloud run deploy "${BITBUCKET_REPO_SLUG}" --region="${r}" --image="${IMAGE}" ...
            done
        artifacts:
          - regions.ssv

  custom:
    deploy-one-region:
      - variables:
          - name: REGION
            default: us-central1
      - step:
          name: Validate region and mock deploy
          script:
            - *fetch-regions   # fails hard if REGION not in active_regions
            - echo "mock deploy region=${REGIONS}"
```

**Service application code**

No change required for mock deploys. For a real service you only need a deploy command that accepts a region (CLI flag, env, or manifest path). Example contract:

```text
deploy.sh --region us-central1 --image $IMAGE
```

The pipeline supplies `--region` from the `$REGIONS` loop; the app does not fetch `regions.yaml` itself.

### Pros / cons

| Pros | Cons |
|------|------|
| No Docker registry or Marketplace | Trust model = download remote script (pin + checksum) |
| Works on any image with curl + python3 | Slightly more boilerplate than `pipe:` |
| Easy public tutorial | PyYAML may need install on slim images |
| Shares parser with GitHub | |

---

## Option B — Bitbucket Pipe (Docker)

### Summary

Publish a versioned pipe image (e.g. `ghcr.io/tunnelwithac/fetch-regions-pipe:1.0.0`) from this repo. The image wraps the **same** `parse_regions.py`. Consumers use `pipe:` then `source` an env file to get `REGIONS`.

Closest UX to a GitHub Action on Bitbucket Cloud.

### What this repo provides

| Path / artifact | Role |
|-----------------|------|
| `bitbucket/pipe/Dockerfile` | Image with parser + entrypoint |
| `bitbucket/pipe/pipe.yml` | Pipe metadata / variable docs |
| `scripts/parse_regions.py` | Shared validation |
| GHCR (or Docker Hub) image tags | Versioned distribution |

**Pipe variables (inputs)**

| Variable | Default | Notes |
|----------|---------|--------|
| `CONFIG_REPO` | `tunnelWithAC/multi-region-deployments` | |
| `CONFIG_PATH` | `config/regions.yaml` | |
| `CONFIG_REF` | pin to tag/SHA | Avoid floating `main` until it exists |
| `REGION` | _(empty)_ | Optional single region / fail-hard |
| `CONFIG_TOKEN` | _(empty)_ | Only for private config (not default) |

**Outputs written into the clone**

```text
.bitbucket/multi-region/regions.env   # export REGIONS='…' etc.
.bitbucket/multi-region/regions.txt   # one-line SSV
.bitbucket/multi-region/regions.json
```

Later steps `source` the env file and/or declare artifacts when crossing steps.

### Microservice implementation (Bitbucket)

What the **service repo** must add:

1. `bitbucket-pipelines.yml` with a fetch step using `pipe: docker://…`.
2. `source .bitbucket/multi-region/regions.env` before deploy.
3. `artifacts` if a later step needs `REGIONS`.
4. Deploy loop identical to Option A.

**Example `bitbucket-pipelines.yml`**

```yaml
image: atlassian/default-image:4

definitions:
  steps:
    - step: &fetch-regions
        name: Fetch active regions
        script:
          - pipe: docker://ghcr.io/tunnelwithac/fetch-regions-pipe:1.0.0
            variables:
              CONFIG_REF: "v1.0.0"
              # REGION: us-central1
          - source .bitbucket/multi-region/regions.env
          - echo "REGIONS=${REGIONS}"
          - test -n "${REGIONS}"
        artifacts:
          - .bitbucket/multi-region/**

pipelines:
  default:
    - step: *fetch-regions
    - step:
        name: Mock deploy all regions
        script:
          - source .bitbucket/multi-region/regions.env
          - |
            for r in ${REGIONS}; do
              echo "mock deploy ${BITBUCKET_REPO_SLUG} → ${r} @ ${BITBUCKET_COMMIT}"
            done

  custom:
    deploy-one-region:
      - variables:
          - name: REGION
      - step:
          name: Fetch and validate one region
          script:
            - pipe: docker://ghcr.io/tunnelwithac/fetch-regions-pipe:1.0.0
              variables:
                CONFIG_REF: "v1.0.0"
                REGION: ${REGION}
            - source .bitbucket/multi-region/regions.env
            - echo "mock deploy → ${REGIONS}"
```

**Service application code**

Same as Option A: region is a **deploy parameter**, not something the app fetches. Example:

```bash
# scripts/deploy.sh (in the microservice repo)
#!/usr/bin/env bash
set -euo pipefail
REGION="${1:?region required}"
IMAGE="${2:?image required}"
echo "Deploying ${IMAGE} to ${REGION}"
# gcloud run deploy "$SERVICE" --region="$REGION" --image="$IMAGE"
```

Pipeline:

```bash
for r in $REGIONS; do ./scripts/deploy.sh "$r" "$IMAGE"; done
```

### Pros / cons

| Pros | Cons |
|------|------|
| Best “Action-like” UX (`pipe:`) | Must build/publish/version an image |
| Host job may not need PyYAML | Artifacts/`source` required across steps |
| Sealed dependencies inside image | Heavier for a first public tutorial |
| Easy semver pins on the image | No true dynamic matrix (use loop or fixed parallels) |

---

## Option C — Shared contract / dual runtime (recommended direction)

### Summary

**One parser, two thin runtimes.**

- `scripts/parse_regions.py` is the only place that understands `regions.yaml` and validation.
- Extend its **stable output contract** so every platform always gets:
  - JSON array (`regions-json` / `REGIONS_JSON`)
  - space-separated string (`regions-ssv` / `REGIONS`)
  - matrix + count for GitHub
- GitHub composite action = fetch + write `$GITHUB_OUTPUT`
- Bitbucket = `fetch-regions.sh` (Option A packaging) calling the same parser
- Optional Docker pipe later = same parser in a container (Option B packaging)

This is not a third fetch mechanism so much as the **architecture** that should sit under A and/or B.

### Contract (parser / both CI systems)

| Output | Example |
|--------|---------|
| `regions-ssv` / `REGIONS` | `us-central1 europe-west1 asia-east1` |
| `regions-json` / `REGIONS_JSON` | `["us-central1","europe-west1","asia-east1"]` |
| `regions-matrix` | `{"region":["us-central1",…]}` |
| `region-count` | `3` |
| Exit `2` | Validation failure (unknown region, empty list, bad names) |
| Exit `1` | I/O / fetch / usage errors |

### What this repo provides

| Artifact | Role |
|----------|------|
| `scripts/parse_regions.py` | SoT: load, validate, select, emit SSV + JSON |
| `scripts/fetch-regions.sh` | Bitbucket/local adapter |
| `.github/actions/fetch-regions` | GitHub adapter (also emit `regions-ssv`) |
| CI drift gate | Fail if action-bundled parser ≠ `scripts/parse_regions.py` |
| `bitbucket/` + `github/` snippets | Consumers |

### Microservice implementation (Bitbucket)

Same consumer shape as **Option A** (curl script), or **Option B** (pipe) once published. The important part for the service team:

| Layer | Responsibility |
|-------|----------------|
| Platform repo | Parse YAML, validate, emit `REGIONS` |
| Microservice pipeline | Pin ref, call wrapper, loop regions, call deploy |
| Microservice app/deploy script | Accept `--region` (and image/tag); no YAML fetch |

**Minimal pipeline (shared-contract + shell adapter)**

```yaml
image: python:3.12-slim

pipelines:
  default:
    - step:
        name: Deploy (mock) to all active regions
        script:
          - set -euo pipefail
          - REF="${REGIONS_REF:-v1.0.0}"
          - BASE="https://raw.githubusercontent.com/tunnelWithAC/multi-region-deployments/${REF}"
          - curl -fsSL --retry 3 "${BASE}/scripts/fetch-regions.sh" -o /tmp/fetch-regions.sh
          - curl -fsSL --retry 3 "${BASE}/scripts/parse_regions.py" -o /tmp/parse_regions.py
          - chmod +x /tmp/fetch-regions.sh
          - eval "$(PARSE_REGIONS_PY=/tmp/parse_regions.py /tmp/fetch-regions.sh --export)"
          - echo "REGIONS=${REGIONS}"   # us-central1 europe-west1 asia-east1
          - |
            for r in $REGIONS; do
              ./scripts/deploy.sh --region "$r" --sha "$BITBUCKET_COMMIT"
            done
```

**Example microservice deploy script**

```bash
#!/usr/bin/env bash
# scripts/deploy.sh — lives in the microservice repository
set -euo pipefail

REGION=""
SHA=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2 ;;
    --sha)    SHA="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

: "${REGION:?--region is required}"
: "${SHA:=unknown}"

echo "Mock deploy ${BITBUCKET_REPO_SLUG:-service} region=${REGION} sha=${SHA}"
# Later (real GCP), still parameterized by REGION only:
# gcloud run deploy "$SERVICE_NAME" \
#   --region="$REGION" \
#   --image="REGION.pkg.dev/PROJECT/REPO/SERVICE:${SHA}"
```

**Optional: validate an orchestrator-supplied region**

When the platform fan-out triggers “deploy only `europe-west1`”:

```yaml
script:
  - export REGION=europe-west1
  - eval "$(…/fetch-regions.sh --export --region "$REGION")"
  # REGIONS is now "europe-west1", or the step failed
  - ./scripts/deploy.sh --region "$REGIONS" --sha "$BITBUCKET_COMMIT"
```

The microservice still does **not** read `regions.yaml`; it only trusts the platform wrapper’s fail-hard check.

### Pros / cons

| Pros | Cons |
|------|------|
| One validation brain for GH + BB | Need to extend parser + keep copies in sync |
| Tutorial can standardize on `REGIONS` SSV | Shell path still has curl boilerplate |
| Pipe can be added later without new rules | Default ref/`main` must exist before public defaults |
| Matches locked “central logic” goal | |

---

## Comparison

| | A Shell script | B Bitbucket Pipe | C Shared contract |
|--|----------------|------------------|-------------------|
| Central logic | Script + parser in this repo | Image embeds parser | Parser is SoT; A/B are adapters |
| Consumer UX | curl + eval | `pipe:` + source | Prefer A now, B optional later |
| `REGIONS` SSV | Yes | Yes | Yes (first-class) |
| GitHub parity | Shared parser | Shared parser | Shared parser **and** outputs |
| Publish burden | None | GHCR + tags | None for v1 |
| Best for | Fast tutorial path | Nicest BB-native UX | Long-term architecture |

---

## Recommendation

1. **Adopt Option C as the architecture** (single parser, stable SSV + JSON contract on GitHub and Bitbucket).
2. **Ship Option A first** (`scripts/fetch-regions.sh` + `bitbucket/` copy-paste) so services can consume without a container registry.
3. **Treat Option B as optional** once the contract is stable, if you want `pipe:` ergonomics.
4. **Microservice contract:** pipelines fetch `REGIONS`; app/deploy scripts only take `--region` (and image/tag). Do not parse `regions.yaml` inside each service.
5. **Pin refs** (tag or SHA) in all public snippets; create/protect `main` before documenting floating defaults.

### Suggested implement order

1. Add `regions-ssv` / shell export support to `parse_regions.py` (and GitHub Action output).
2. Add `scripts/fetch-regions.sh`.
3. Document Bitbucket consumer + example `scripts/deploy.sh` pattern (this file + pipeline snippets).
4. Collapse parser to one copy + CI drift check.
5. (Optional) Docker pipe wrapping the same script/parser.

---

## Validation matrix (all options)

| Input | Result |
|-------|--------|
| No region override | `REGIONS="us-central1 europe-west1 asia-east1"` (from current config) |
| `REGION=europe-west1` | `REGIONS="europe-west1"` |
| `REGION=us-west9` | Step fails (exit 2); enabled regions listed on stderr |
| Missing/empty YAML or HTTP 404 | Step fails (exit 1); no empty `REGIONS` |

---

## Out of scope here

- Live GCP credentials / WIF
- Automated Terraform when a region is added
- Bitbucket-side fan-out orchestrator (platform GitHub workflow remains primary)
- Parsing `tier` / `endpoint_suffix` in deploy loops (illustrative fields only)
