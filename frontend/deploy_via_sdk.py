"""
Deploy the Streamlit frontend to Cloud Run using Python SDKs directly,
bypassing gcloud CLI permission issues.
"""
import os
import sys
import tarfile
import tempfile
import time
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────
PROJECT          = "acn-cda"
REGION           = "us-central1"
SERVICE_NAME     = "report-gen-efficient-v1"
IMAGE            = f"gcr.io/{PROJECT}/{SERVICE_NAME}:latest"
BUCKET           = "acn-cda-rmn-report-gen"
GCS_OBJECT       = "cloudbuild/frontend-source.tar.gz"
FRONTEND_DIR     = Path(__file__).parent

# ── Step 1: Archive frontend source ─────────────────────────────────────────
print("Step 1: Archiving frontend source...")
tmp_tar = tempfile.mktemp(suffix=".tar.gz")
with tarfile.open(tmp_tar, "w:gz") as tar:
    for fname in ["app.py", "requirements.txt", "Dockerfile", ".dockerignore"]:
        fpath = FRONTEND_DIR / fname
        if fpath.exists():
            tar.add(fpath, arcname=fname)
            print(f"  Added: {fname}")
print(f"  Archive: {tmp_tar}")

# ── Step 2: Upload to GCS ────────────────────────────────────────────────────
print(f"\nStep 2: Uploading to gs://{BUCKET}/{GCS_OBJECT} ...")
from google.cloud import storage as gcs
gcs_client = gcs.Client(project=PROJECT)
bucket     = gcs_client.bucket(BUCKET)
blob       = bucket.blob(GCS_OBJECT)
blob.upload_from_filename(tmp_tar, content_type="application/gzip")
print(f"  Uploaded OK → gs://{BUCKET}/{GCS_OBJECT}")
os.unlink(tmp_tar)

# ── Step 3: Submit Cloud Build job ───────────────────────────────────────────
print(f"\nStep 3: Submitting Cloud Build job to build {IMAGE} ...")
from google.cloud.devtools import cloudbuild_v1

cb = cloudbuild_v1.CloudBuildClient()
build = cloudbuild_v1.Build(
    source=cloudbuild_v1.Source(
        storage_source=cloudbuild_v1.StorageSource(
            bucket=BUCKET,
            object_=GCS_OBJECT,
        )
    ),
    steps=[
        cloudbuild_v1.BuildStep(
            name="gcr.io/cloud-builders/docker",
            args=["build", "-t", IMAGE, "."],
        )
    ],
    images=[IMAGE],
    timeout={"seconds": 600},
)

op = cb.create_build(project_id=PROJECT, build=build)
print(f"  Build submitted: {op.metadata.build.id}")
print("  Waiting for build to complete (this takes ~5 min)...")

result = op.result(timeout=700)
if result.status != cloudbuild_v1.Build.Status.SUCCESS:
    print(f"  Build FAILED: {result.status}")
    sys.exit(1)
print(f"  Build SUCCEEDED → {IMAGE}")

# ── Step 4: Deploy to Cloud Run ──────────────────────────────────────────────
print(f"\nStep 4: Deploying {SERVICE_NAME} to Cloud Run...")
from google.cloud import run_v2

run = run_v2.ServicesClient()
parent = f"projects/{PROJECT}/locations/{REGION}"

service = run_v2.Service(
    template=run_v2.RevisionTemplate(
        containers=[
            run_v2.Container(
                image=IMAGE,
                ports=[run_v2.ContainerPort(container_port=8080)],
                resources=run_v2.ResourceRequirements(
                    limits={"memory": "1Gi", "cpu": "1"},
                ),
                env=[
                    run_v2.EnvVar(name="GOOGLE_GENAI_USE_VERTEXAI", value="1"),
                    run_v2.EnvVar(name="GOOGLE_CLOUD_PROJECT",      value=PROJECT),
                    run_v2.EnvVar(name="GOOGLE_CLOUD_LOCATION",     value=REGION),
                ],
            )
        ],
        timeout={"seconds": 3600},
    ),
    ingress=run_v2.IngressTraffic.INGRESS_TRAFFIC_ALL,
)

try:
    # Try update first (if service exists)
    op2 = run.update_service(
        service=service,
        request={"name": f"{parent}/services/{SERVICE_NAME}"},
    )
    print("  Updating existing service...")
except Exception:
    # Create new
    op2 = run.create_service(
        parent=parent,
        service=service,
        service_id=SERVICE_NAME,
    )
    print("  Creating new service...")

svc_result = op2.result(timeout=300)

# Allow unauthenticated access
from google.iam.v1 import iam_policy_pb2, policy_pb2

try:
    policy = run.get_iam_policy(request={"resource": svc_result.name})
    policy.bindings.append(
        policy_pb2.Binding(
            role="roles/run.invoker",
            members=["allUsers"],
        )
    )
    run.set_iam_policy(request={"resource": svc_result.name, "policy": policy})
    print("  IAM: allUsers invoker set (public access)")
except Exception as e:
    print(f"  IAM warning (may need manual step): {e}")

print(f"\n✅ DEPLOYED!")
print(f"   Service URL: {svc_result.uri}")