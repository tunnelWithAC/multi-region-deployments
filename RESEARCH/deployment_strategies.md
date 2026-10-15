You can automatically trigger deployments across all microservices whenever a new region is added to your shared registry.

To achieve this, you need an event-driven CI/CD architecture where a commit to your `global-platform-config` repository acts as a trigger for all downstream microservice repositories.

---

### Implementation Options

* **Option 1: Webhook Fan-Out (Fastest Automation)**
* **How it works:** When a pull request modifying `regions.yaml` is merged into your platform config repo, a webhook or a Google Cloud Eventarc trigger fires.
* **Execution:** A centralized automation script (running in Cloud Functions or Cloud Build) reads the updated region list, loops through your registered microservices via API (e.g., GitHub or GitLab API), and programmatically dispatches a workflow dispatch event (or triggers a pipeline) for each microservice repository, passing the new region as a parameter.


* **Option 2: GitOps with Config Sync / ArgoCD (Declarative & Resilient)**
* **How it works:** Instead of pushing code via CI/CD pipelines, your microservices are deployed via a GitOps tool like **Google Cloud Deploy** or **Argo CD** pointing to a target state repository.
* **Execution:** When a new region is added to `regions.yaml`, a script or a platform operator automatically generates or updates the target Kubernetes manifests / Cloud Run configurations for that new region. The GitOps engine detects the change and automatically provisions the microservices in the new region without needing to touch individual microservice source code repos.
