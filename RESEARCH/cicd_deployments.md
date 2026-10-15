To automatically roll out services to a new region as soon as it is added to your configuration repository, you can combine a **Bitbucket Repository Push Webhook** with your internal tool or a lightweight orchestrator script.

Because your infrastructure is managed via **Terraform** and **gcloud**, the new region must first be provisioned at the infrastructure layer before microservices can safely target it.

---

### Step-by-Step Architecture for Automated Region Rollout

```
[ Platform Config Repo ] ---> ( Push to regions.yaml )
         │
         ▼
[ Bitbucket Webhook ] ---> [ Internal Tool / Function ]
                                 │
            ┌────────────────────┴────────────────────┐
            ▼                                         ▼
   1. Run Terraform Apply                2. Trigger Bitbucket Pipelines
     (Provision GCP regions)                (Roll out microservices via API)

```

#### 1. Capture the Region Addition Event via Webhooks

* Configure a **Repository Webhook** on your `mutli-region-manager` repository in Bitbucket.
* Set the trigger event to **Repository: Push**.
* Point the webhook URL to an endpoint hosted by your internal tool (or a serverless function like Google Cloud Run / Cloud Functions) that listens for changes to `regions.yaml`.

#### 2. Automate Infrastructure Provisioning with Terraform

When your internal tool receives the webhook payload indicating that a new region has been appended to `regions.yaml`:

* The service clones the latest platform config and runs a Terraform script.
* Use a Terraform map or `for_each` loop tied to your regions configuration so Terraform automatically provisions regional prerequisites (e.g., GCP subnets, GKE/Cloud Run bindings, IAM roles, or Artifact Registry repository settings) for the newly added region without tearing down existing ones.
* *Verification Step:* Run `terraform plan` to confirm that only the resources for the newly added region are targeted for creation.

#### 3. Fan-Out Bitbucket Pipelines to Microservice Repositories

Once Terraform successfully finishes provisioning the infrastructure in the new region:

* Your internal tool uses the **Bitbucket REST API** to loop through your microservice repositories.
* It programmatically triggers a pipeline execution (using the Bitbucket Pipeline API endpoint) for each service repo, passing the newly added region name as a pipeline runtime variable.
* Inside each microservice repository, the Bitbucket pipeline reads that variable and deploys the container image into the new GCP region using native `gcloud` commands or regional kubecontexts.
* *Verification Step:* Check the Bitbucket Pipelines dashboard across your service repos to verify that the parameterized deployment jobs finish with a success status.
