To centralize your multi-region configuration and allow consumer Bitbucket repositories to fetch the list of regions dynamically with minimal boilerplate, the best approach is to use the **Bitbucket REST API** combined with `yq` in a short bash snippet.

This ensures that if you add, remove, or modify regions in your central config repo, consumer pipelines automatically pull the latest state without needing code changes.

---

### Step 1: Generate a Bitbucket App Password (or Access Token)

To let consumer pipelines query a private repository via the API, they need authentication:

1. Go to your Bitbucket account or workspace settings and create an **App Password** (or a Repository Access Token) with at least **`repository:read`** scope.
2. Store this token as a secure **Repository Variable** (e.g., `BB_CONFIG_TOKEN`) in the consumer repositories (or globally at the workspace level so you never have to configure it per repo).

---

### Step 2: The Consumer Pipeline Snippet

In any consumer repository's `bitbucket-pipelines.yml`, you can fetch and parse the yaml file directly from the central repo on the fly using `curl` and `yq`.

Add this step to your pipeline:

```yaml
pipelines:
  default:
    - step:
        name: Fetch Regions from Central Config
        image: alpine/git:latest # or any image with curl and yq
        script:
          - apk add --no-cache curl yq
          
          # 1. Fetch the raw YAML file from your central private repository branch (e.g., main)
          - |
            ACTIVE_REGIONS=$(curl -s -u "x-token-auth:$BB_CONFIG_TOKEN" \
              "https://api.bitbucket.org/2.0/repositories/YOUR_WORKSPACE/YOUR_CONFIG_REPO/src/main/path/to/config.yaml" \
              | yq '[.active_regions[].name] | join(" ")')

          # 2. Export or use the variable
          - echo "Regions are -> $ACTIVE_REGIONS"
          
          # Example of passing it down or using it in a command
          - ./deploy.sh --regions "$ACTIVE_REGIONS"

```

---

### Why this is the best approach:

* **Zero Consumer Maintenance:** If you change regions or add a new one in the central repo's YAML file, consumer pipelines pick it up instantly on their next run without changing a single line of their own pipeline configuration.
* **Centralized Logic:** All structure and mapping stay tightly bound to your single config repository.
* **Clean Parsing:** Using `yq` with the `join(" ")` filter converts the YAML array list directly into the exact space-separated string format (`us-central1 europe-west1 asia-east1`) natively.
