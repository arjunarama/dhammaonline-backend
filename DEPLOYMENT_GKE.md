# Deploying a FastAPI Backend to Google Kubernetes Engine (GKE)

A step-by-step learning guide for taking a small FastAPI app from local development to a managed Kubernetes cluster on Google Cloud. Written while actually doing it on **dhammaonline-backend**, a hobby project.

> **Stack being deployed:** FastAPI + SQLModel + Pydantic + python-jose (JWT) + bcrypt + Cloudinary (media). Currently runs locally on SQLite.
>
> **Sequencing note:** We deploy **twice on purpose**. The first deploy ships the app as-is — SQLite inside the container. That gets you a real running GKE service end-to-end, but the data is **ephemeral** (any pod restart wipes the DB). Then in Phase 11 we swap SQLite → **MongoDB Atlas (free M0 tier)** and redeploy. The double pass is intentional — you'll learn the "rebuild image + roll out a new version" loop, which is the bulk of real-world Kubernetes work.

---

## What you'll learn

- What containers, Kubernetes, and GKE actually are (in plain English)
- How to containerize a Python web app with Docker
- How to push images to Google Artifact Registry
- How to provision managed Postgres on Cloud SQL
- How to manage secrets in Kubernetes
- How to create a GKE Autopilot cluster
- How to write Deployment, Service, and Ingress manifests
- How to map a domain and enable HTTPS with a managed cert
- How to update CORS to point your frontend at the new backend

---

## Cost warning (read this before you start)

A GKE Autopilot cluster running a single small FastAPI pod costs roughly **\$70–80 / month** (mostly the \$0.10/hr cluster management fee + minimal pod CPU/RAM). If you also add MongoDB Atlas (Phase 11) on the free **M0 tier**, that's an extra **\$0** — M0 is genuinely free, no credit card needed, just rate-limited and capped at 512 MB.

For a hobby project, ~\$75/month is real money. You have three choices:

1. **Keep it running** — accept the cost.
2. **Learn and tear down** — go through the whole journey, then delete the cluster to stop billing. You'll still learn everything.
3. **Use the GCP free trial** — \$300 credit / 90 days for new accounts. Easily covers the entire journey including Phase 11.

The guide includes a **"How to tear it down"** section at the end so nothing keeps billing you after you're done.

---

## The 11-phase journey

| # | Phase | Status |
|---|-------|--------|
| 0 | Prerequisites & concepts | ✅ Done |
| 1 | Containerize the FastAPI app (with SQLite inside, ephemeral) | ✅ Done |
| 2 | GCP project setup (+ enable APIs) | ✅ Done |
| 3 | Push image to Artifact Registry | ✅ Done |
| 4 | Configure application secrets (JWT, Cloudinary) | ⏭️ Skipped for first deploy (app boots with no secrets) |
| 5 | Create Kubernetes Secret objects | ⏭️ Skipped for first deploy |
| 6 | Create the GKE Autopilot cluster | ✅ Done |
| 7 | Write Kubernetes manifests | ✅ Done |
| 8 | Deploy & verify (LIVE 🎉) | ✅ Done |
| 9 | Domain + HTTPS | ⚪ Pending |
| 10 | Update frontend CORS | ⚪ Pending |
| 11 | Migrate SQLite → MongoDB Atlas (free M0) and redeploy | ⚪ Pending |

---

## Phase 0 — Prerequisites & concepts

### Concepts in plain English

**Container** — a lightweight, self-contained box holding your app's code, its Python interpreter, its libraries, and everything it needs to run. It's like shipping your whole laptop's project folder *plus* the exact Python install — but tiny. Built with **Docker**, runs anywhere.

**Image** — a snapshot/blueprint of a container. You build the image once; you can start many containers from it. Stored in registries like Docker Hub or **Artifact Registry** (GCP's version).

**Kubernetes (K8s)** — an orchestrator. You hand it your containers and tell it "run 3 copies of this, give it 1 GB of memory, expose it on port 8000, restart it if it crashes." It does all that, plus rolling updates, load balancing, self-healing.

**GKE (Google Kubernetes Engine)** — Kubernetes-as-a-Service from Google. You don't have to install or maintain Kubernetes itself — Google runs the control plane; you just bring your containers and manifests.

**GKE Autopilot vs Standard** — Autopilot means Google also manages the underlying machines (nodes) — you only pay for what your pods use. Standard means you manage the nodes yourself (cheaper at scale, more work). We're using **Autopilot** because this is a learning + small-scale project.

**Manifests** — YAML files describing what you want running. `Deployment` (the app), `Service` (network address inside the cluster), `Ingress` (how the outside world reaches your app).

**Pod** — the smallest unit Kubernetes runs. Usually one container per pod (though it can be more). Think of it as one instance of your app.

**Ephemeral filesystem** — when a pod restarts (crashes, gets rescheduled, or you push a new image), it starts from a fresh copy of the image. Any files written *inside* the container while it was running are **gone**. This is why we don't store SQLite databases or uploaded files in the container itself — for real persistence you need an external database (MongoDB Atlas) or object storage (Cloudinary). Phases 1–10 deliberately ignore this so you feel the pain; Phase 11 fixes it.

---

### The hierarchy: Cluster → Node → Pod (plain English)

The single most useful mental model. A **cluster is NOT one computer** — it's a *group* of machines managed as one unit, plus a "brain" that coordinates them:

```
Cluster                         ← the whole managed group (a mini data-center)
 ├─ Control plane               ← the "brain" — Google runs this for you
 └─ Nodes                       ← the machines (rented VMs in Google's data centers)
     ├─ Node 1  →  runs Pods    ← a node = ONE machine
     ├─ Node 2  →  runs Pods
     └─ Node 3  →  runs Pods
         └─ Pod → your container → your app
```

| Term | Plain meaning |
|------|---------------|
| **Cluster** | the whole managed group of machines (the "factory" / mini data-center) |
| **Node** | **one machine** in that group (a rented VM — you don't own hardware) |
| **Pod** | one running copy of your container, placed *on* a node |
| **Workload** (a Deployment) | the standing instruction "keep N pods of my app running" — what shows under **Workloads** in the console |
| **Service** | the public doorway/IP that routes traffic to those pods |

Key points that trip people up:
- You **don't choose which node** a pod runs on — Kubernetes places each pod on whichever node has room. That scheduling *is* its core job.
- The nodes are **rented VMs**, not a physical box you own; you pay for time on Google's hardware.
- **Autopilot vs Standard shows up here:**
  - *Autopilot* (this project) — you never see or manage nodes; Google **creates a machine on demand** when a pod needs one. (That's exactly why a freshly-deployed pod sits in `Pending` for a minute — Autopilot is spinning up a node to place it on.)
  - *Standard* (e.g. the OpenSky cluster, which runs `NUM_NODES: 5`) — a human picks and manages a fixed set of machines.
- **One cluster can run many workloads**, isolated by **namespaces** (think rooms in the factory). OpenSky runs stage and prod as two namespaces in a *single* cluster — not two clusters.

---

### Tooling you need on your machine

| Tool | Why | How to get it |
|------|-----|---------------|
| **Docker Desktop** | Build container images, test them locally | https://www.docker.com/products/docker-desktop |
| **Google Cloud SDK (`gcloud`)** | Talk to GCP from your terminal | https://cloud.google.com/sdk/docs/install |
| **`kubectl`** | Talk to your Kubernetes cluster | Installed via `gcloud components install kubectl` |
| **A GCP account with billing enabled** | Required for GKE | https://console.cloud.google.com |

We'll install these as we need them. For Phase 0, we install **Docker Desktop**, **gcloud SDK**, and **enable billing on a GCP account** (free trial works).

> **Windows shortcut for gcloud:** instead of the installer EXE, you can use winget — `winget install --id Google.CloudSDK --source winget`. Takes ~2 min and puts `gcloud` on PATH automatically. You must close + reopen your terminal afterward.

> **kubectl note:** Docker Desktop on Windows now bundles kubectl by default, so you may already have it. Check with `kubectl version --client`. If not, `gcloud components install kubectl` later works fine.

---

### Step 0.1 — Install Docker Desktop (Windows)

1. Go to https://www.docker.com/products/docker-desktop and click **Download for Windows** (the AMD64 / x64 build).
2. Run the downloaded `Docker Desktop Installer.exe`.
3. In the installer, **leave "Use WSL 2 instead of Hyper-V" checked** (it's the default). Docker uses Windows Subsystem for Linux 2 to run Linux containers efficiently.
4. Let the installer finish — takes a few minutes.
5. **Reboot when asked.** Docker will not work until you reboot.
6. After reboot, launch **Docker Desktop** from the Start menu.
7. First launch shows a setup screen — accept the terms, skip the survey if you want.
8. Wait for the **whale icon in the system tray** (bottom-right of the taskbar, near the clock — you may need to click the `^` to see hidden icons) to stop animating. When it's steady, Docker is running.
9. Open a **new** PowerShell window (existing windows won't pick up the new PATH) and verify:
   ```powershell
   docker --version
   docker run hello-world
   ```
   The second command should pull a tiny test image and print "Hello from Docker!".

**Troubleshooting:**

| Symptom | Likely cause | Fix |
|---|---|---|
| `'docker' is not recognized as the name of a cmdlet…` | Docker Desktop not installed yet, OR you're using a PowerShell window opened before install | Finish the install + reboot, then open a **fresh** PowerShell window |
| `docker run hello-world` hangs or says "Docker daemon not running" | Docker Desktop isn't actually running | Make sure the whale icon is visible and steady in the system tray |
| WSL 2 install fails during Docker install | WSL not bootstrapped | Open PowerShell as Administrator → run `wsl --install` → reboot → retry the Docker installer |
| Windows Home edition | Hyper-V isn't available | Docker Desktop *requires* WSL 2 on Home — that's fine, just keep the WSL 2 checkbox checked |

---

### Step 0.2 — Set up GCP billing (free trial)

Without billing, you can't create paid resources like GKE clusters. We'll use the **free trial** so this learning exercise costs you nothing.

1. Go to https://console.cloud.google.com/freetrial (or the free-trial banner inside https://console.cloud.google.com).
2. Sign in with your Google account. Accept the terms.
3. Enter your payment method (credit or debit card). **Yes, a card is required even for the free trial** — Google uses it for identity verification to block abuse. See the FAQ below if this makes you nervous.
4. Submit. You'll land on a "Welcome to Google Cloud" screen with **\$300 USD of credit** available for **90 days**.
5. A default project (often named "My First Project") is created automatically. We'll rename it / create a dedicated one in Phase 2.

**Note:** Setting up billing does *not* charge you immediately. Charges only happen when you create paid resources, and those are covered by the \$300 credit until it runs out or 90 days pass — whichever comes first.

#### FAQ — "Is it safe to give Google my debit card?"

| Question | Answer |
|---|---|
| **Will Google charge my card during the trial?** | No. The \$300 credit covers everything. You may see a small temporary auth (often \$0–\$1) which is refunded within a few days — that's identity verification, not a charge. |
| **What happens when the trial ends (90 days or \$300 used)?** | Your account moves to a *paused* state. Resources keep existing but stop running. **You are not auto-billed.** Charges only begin if you manually click "Activate full account". |
| **Can I cancel / scrap the account later?** | Yes, fully. Delete the project (kills all resources), close the billing account, and remove the card from Payment Methods. Zero charges, ever, as long as you don't manually activate full billing. |
| **Do debit cards work?** | Usually yes. Some *prepaid* or *virtual* cards get rejected. If your card is declined, try a different one before assuming the trial is broken. |
| **Can I do all this without a card?** | No, not for GKE. Only the free tier of *some* services (e.g. MongoDB Atlas M0, which we use in Phase 11) is card-free. GKE itself requires billing setup. |

---

### Step 0.3 — Install gcloud SDK

On Windows the fastest path is **winget**:

```powershell
winget install --id Google.CloudSDK --source winget
```

This installs to `C:\Users\<you>\AppData\Local\Google\Cloud SDK\` and adds it to PATH. Takes ~2 minutes.

**You must close and reopen your terminal afterward** — the current shell won't see the new PATH.

Verify:

```powershell
gcloud --version
```

You should see `Google Cloud SDK 5xx.x.x` and a list of components.

Then initialize:

```powershell
gcloud init
```

This walks you through:
- Logging in via browser (opens automatically)
- Picking a default project (the one auto-created with your free trial)
- Picking a default region/zone (use `us-central1` and `us-central1-a` unless you have a reason not to — most tutorials assume this and it has the best service coverage)

**Don't have winget?** (Older Win10.) Use the installer EXE from https://cloud.google.com/sdk/docs/install instead — same end result.

---

### Step 0.4 — Sanity check before moving on

You should now have:

- [ ] Docker Desktop installed, running, and `docker run hello-world` works
- [ ] `kubectl version --client` works (came with Docker Desktop, or installed separately)
- [ ] `gcloud --version` works in a fresh terminal
- [ ] `gcloud init` completed — you're logged in with a default project + region set
- [ ] GCP free trial active (\$300 / 90 days)

When all five boxes are checked, we move to **Phase 1: Containerizing the FastAPI app**.

---

## Phase 1 — Containerize the FastAPI app

Goal: turn the app into a Docker **image** that runs identically anywhere. For this first pass the database is **SQLite inside the container** — deliberately ephemeral (Phase 11 fixes persistence).

### Why this app is easy to containerize
We checked the code first, and it boots with **zero required env vars**:
- `database.py` → `DATABASE_URL` defaults to `sqlite:///dhammaonline.db`
- `auth.py` → `JWT_SECRET_KEY` has a dev default
- `cloudinary_config.py` → reads keys via `os.getenv()` with no default; missing keys just make image uploads fail, the app still boots
- `main.py` exposes `GET /` returning `{"message": "..."}` (a natural health-check target) and `@app.on_event("startup")` creates the tables

So the **first deploy needs no secrets at all**. We add real secrets + a real database later.

### Files added
**`Dockerfile`**
```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt   # own layer → cached
COPY . .
EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
```
Key ideas: `python:3.12-slim` (lean base; psycopg2-binary & bcrypt ship wheels so no compiler needed); copy `requirements.txt` *before* the code so the slow `pip install` layer is **cached** and only re-runs when deps change; `--host 0.0.0.0` so the container accepts outside traffic; shell-form `CMD` so `${PORT}` expands.

**`.dockerignore`** — keeps `venv/`, `__pycache__/`, `.git/`, `.env` (secrets!), `*.db` (local data) and the k8s/docs files out of the image. Smaller, safer images.

**`k8s/deployment.yaml`** and **`k8s/service.yaml`** — added now, used in Phases 7–8.

### Gotcha we hit: `requirements.txt` was UTF-16
The file was saved as UTF-16 (every character spaced out, with a BOM). `pip install` inside Docker can choke on that. **Fix:** re-saved it as plain UTF-8. If your `pip install` step ever fails with weird encoding/parse errors, check the file encoding first.

### Test it locally (before any cloud)
```powershell
cd dhammaonline-backend
docker build -t dhammaonline-backend:local .
docker run --rm -p 8080:8080 dhammaonline-backend:local
# open http://localhost:8080/  → {"message":"Dhamma Online FastAPI Backend Running"}
# Ctrl+C to stop
```
`-p 8080:8080` maps your laptop's port 8080 → the container's 8080. `--rm` deletes the container when you stop it. A green response means the image is good and we can push it to the cloud.

## Phase 2 — GCP project setup + enable APIs

### Project: name vs ID (a common confusion)
Every project has **two** identifiers:
- a **display name** ("My First Project") — cosmetic, shown in the console, renameable
- a **project ID** (`project-4574476e-e192-4209-9d6`) — globally unique, permanent, what every command uses

The console showing "My First Project" while gcloud uses the ID is **not a mismatch** — same project. To rename the display name:
```powershell
gcloud projects update <PROJECT_ID> --name="dhammaonline"
```

### Installing gcloud (Windows) + the PATH gotcha
```powershell
winget install --id Google.CloudSDK --source winget --accept-source-agreements --accept-package-agreements --silent
```
**Gotcha:** the installer adds gcloud to PATH, but **terminals already open won't see it**. Either open a brand-new terminal, or add it to the current session:
```powershell
$env:Path += ";$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin"
```

### Authenticate (must be done in your own terminal — browser flow)
```powershell
gcloud auth login                                  # opens browser → pick account → Allow
gcloud config set project <PROJECT_ID>             # set default project
```
The token caches under your user profile, so subsequent commands (and tools acting as you) reuse it.

### Enable the APIs
GCP services are off by default. Turn on the two we need:
```powershell
gcloud services enable artifactregistry.googleapis.com container.googleapis.com
```

---

## Phase 3 — Push the image to Artifact Registry

**Artifact Registry** = your private cloud "shelf" for Docker images. The cluster pulls from here.

### Create the repo
```powershell
gcloud artifacts repositories create dhamma-repo `
  --repository-format=docker `      # holds Docker images
  --location=us-central1 `          # region the images live in
  --description="dhammaonline backend images"
```

### Let Docker authenticate to it
```powershell
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet
```
**Gotcha (Windows):** this prints `python.exe : Adding credentials...` painted as a red error. It's **not** an error — gcloud writes status to stderr and PowerShell colours it red. The real outcome is `Docker configuration file updated`.

### Tag + push
An image's "name" *is* its address. To send it to the cloud you relabel (**tag**) it with the registry path, then **push**:
```powershell
$IMG = "us-central1-docker.pkg.dev/<PROJECT_ID>/dhamma-repo/dhammaonline-backend:v1"
docker tag dhammaonline-backend:local $IMG
docker push $IMG
```
A digest line (`v1: digest: sha256:… size: …`) means it's stored. You can see it in console under **Artifact Registry → dhamma-repo**.

> **On secrets (Phases 4–5): skipped for the first deploy.** We checked the code — the app boots with zero env vars (SQLite default, dev JWT default, Cloudinary no-ops). So the first deploy ships nothing secret. We'll add real secrets when we add a real database (Phase 11) and lock down JWT/Cloudinary.

---

## Phase 6 — Create the GKE Autopilot cluster

```powershell
gcloud container clusters create-auto dhamma-cluster-mum --location=asia-south1
```
`create-auto` = **Autopilot** (Google manages the nodes; you only pay for what pods use). It's **regional** (a region, not a single zone) for resilience. Provisioning takes **~5-9 minutes** — normal. Watch it in console under **Kubernetes Engine → Clusters**.

### Which region? (we switched us-central1 → asia-south1)
The region is baked into the cluster — you can't move it later, only recreate. Pick based on **where your users are**:
- **`us-central1`** — the tutorial default; ~250 ms round-trip from India.
- **`asia-south1` (Mumbai)** — ~30-50 ms from India, and it matches where the OpenSky backend already runs, so the learning transfers 1:1.

We started on us-central1 (guide default), then recreated in Mumbai. **The image stayed in the us-central1 registry** — a cluster can pull from a registry in a different region (cross-region pull, costs a few cents once). Registry region and cluster region are independent.

### Gotcha: free-trial CPU quota fits only ONE Autopilot cluster
A fresh Autopilot cluster reserves **8 vCPUs**, and the free trial's **`CPUS_ALL_REGIONS` quota is 12**. So you can't have two clusters at once — creating the Mumbai one while us-central1 still existed failed with:
```
429 ... resource "CPUS_ALL_REGIONS": request requires '8.0' and is short '4.0'
```
**Fix:** fully delete the old cluster first (frees its 8 CPUs), *then* create the new one:
```powershell
gcloud container clusters delete dhamma-cluster --location=us-central1 --quiet
# wait until it's gone, then create the Mumbai cluster
```
(You also can't delete a cluster while it's still `PROVISIONING` — wait for `RUNNING` first. Deletion shows as `STOPPING`.)

## Phase 7 — Write the Kubernetes manifests

Two YAML files in `k8s/`. Manifests are *declarative* — you describe the desired end state, Kubernetes makes reality match.

**`k8s/deployment.yaml`** — the **workload**: "run my image as a pod, keep it healthy."
- `replicas: 1` — one copy.
- `image:` — the full Artifact Registry path of the image to run.
- `resources.requests` — **Autopilot requires this** (cpu `250m` = ¼ core, memory `512Mi`). It's how Autopilot decides what size node to provision.
- `readinessProbe` / `livenessProbe` on `GET /` — readiness gates traffic until the app answers; liveness restarts a wedged pod. We reuse the existing `/` route (returns 200).

**`k8s/service.yaml`** — the **doorway**: `type: LoadBalancer` asks GCP for a public IP and forwards port 80 → the pod's 8080.

## Phase 8 — Deploy & verify

```powershell
# point kubectl at the cluster
gcloud container clusters get-credentials dhamma-cluster-mum --location=asia-south1
# hand the cluster your desired state
kubectl apply -f k8s/
```
Output: `deployment.apps/... created` + `service/... created`.

Watch it come up:
```powershell
kubectl get pods -l app=dhammaonline-backend     # want STATUS=Running, READY 1/1
kubectl get service dhammaonline-backend          # EXTERNAL-IP <pending> → real IP in ~1-2 min
```

### Two normal "wait" states
- **Pod `Pending`** for a minute — Autopilot is creating a node for it (no node existed yet).
- **`EXTERNAL-IP <pending>`** — GCP is provisioning the load balancer + public IP.

### ⚠️ Gotcha we hit: `ImagePullBackOff` → 403 Forbidden
The pod couldn't pull the image:
```
failed to authorize: ... 403 Forbidden
```
**Cause:** the cluster's node **service account** (the default compute SA, `<PROJECT_NUMBER>-compute@developer.gserviceaccount.com`) didn't have permission to read Artifact Registry. Building + pushing an image isn't enough — *the cluster's identity must be allowed to pull it.* (This is permission, not region — same error would happen same-region.)

**Fix:** grant the role, then restart so it re-pulls:
```powershell
$num = gcloud projects describe <PROJECT_ID> --format="value(projectNumber)"
gcloud projects add-iam-policy-binding <PROJECT_ID> `
  --member="serviceAccount:$num-compute@developer.gserviceaccount.com" `
  --role="roles/artifactregistry.reader" --condition=None

kubectl rollout restart deployment dhammaonline-backend
```
IAM takes ~1-2 min to propagate; the pod retries automatically (or the restart forces a fresh pull).

### ✅ Verified live
```
GET http://<EXTERNAL-IP>/        → {"message":"Dhamma Online FastAPI Backend Running"}
GET http://<EXTERNAL-IP>/teachings → []   (empty — fresh ephemeral SQLite, as designed)
GET http://<EXTERNAL-IP>/docs     → FastAPI Swagger UI
```
The backend is now running on GKE Autopilot in Mumbai, reachable on a public IP. **Data is still ephemeral** (SQLite inside the pod) — a pod restart wipes it. That's what Phase 11 fixes.

<!-- Phases 9–11 (domain+HTTPS, CORS, persistent DB) added as we work through them. -->



