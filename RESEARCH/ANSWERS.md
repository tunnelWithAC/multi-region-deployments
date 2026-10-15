

### Scope & success
1. **Deliverable bar** — docs + reusable fetch action only, working E2E demo, mock/dry-run pipelines, or full platform (incl. infra on region add)? mock/dry-run pipelines
2. **Audience** — personal/portfolio, internal reference, public tutorial, or spike for a real rollout? public tutorial
3. **Example service** — what should `multi-region-microservice-example` contain (minimal hello-world, realistic API, pipelines only)? minimal hello-world

### Runtime & CI
4. **Deploy target** — mock only, Cloud Run, GKE, or pluggable abstract step? mock only
5. **Real GCP?** — credentials/WIF and a real project in scope, or dry-run with docs for how auth would plug in? dry run
6. **CI platforms** — implement GitHub and Bitbucket equally, or one primary with the other as docs/snippets? github primary with bitbucket docs
7. **Infra on new region** — Terraform/IaC before fan-out in scope, assume capacity exists, or document-only? document only

### Region lifecycle & fan-out
8. **New region** — how should fan-out work (orchestrator/webhook API-triggering each service, central dispatch workflow, GitOps, docs only)? orchestrator/webhook API-triggering each service, 
9. **Service registry** — only the example repo, hardcoded list, `services.yaml` next to `regions.yaml`, org discovery, or out of scope? `services.yaml` 
10. **Code-change deploys** — all active regions (matrix), single region param with validation, primary-tier default, or optional override? all active regions
11. **Region remove/demote** — out of scope (add-only), block new deploys, trigger teardown, or document options only? document options
12. **`tier` / `endpoint_suffix` in `regions.yaml`** — used by pipelines (e.g. primary-only, DNS naming), or illustrative fields for later? illustrative fields for later

### Shared config fetch & ownership
13. **Fetch mechanism** — reusable GitHub Action + Bitbucket script, public raw URL, curl+checksum script, submodule, or something else? reusable GitHub Action + Bitbucket script
14. **Auth to read `regions.yaml`** — public repo OK, or private with token/App? public repo OK
15. **Where does the webhook/orchestrator live** — this repo’s workflows, Cloud Function/Run, external tool, or not implemented in v1? this repo
16. **Validation failure** — fail the job hard if region not in config; warn only; or allow break-glass override? fail

### Docs
17. **Doc shape** — README architecture + copy-paste snippets, full tutorial walkthrough, or ADRs + examples under `github/` and `bitbucket/`? README architecture + copy-paste snippets
18. **Must-show flows** — (a) region added → fan-out deploy, (b) service change → validate + multi-region deploy, (c) both, (d) anything else (rollback, partial failure)? c
