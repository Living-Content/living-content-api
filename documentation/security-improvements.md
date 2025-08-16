# Security Implementation Plan

## What We're Building

A two-registry system with mandatory verification for all container images:

- **Incoming Registry**: Where developers push unsigned images
- **Trusted Registry**: Where verified images are promoted
- **Admission Control**: Kubernetes only runs images from trusted registry

## Implementation Steps

### 1. Infrastructure Setup

#### Create Registries

```bash
# Quarantine registry for initial pushes
gcloud artifacts repositories create project-images-incoming \
  --repository-format=docker \
  --location=us-central1

# Production registry already exists: project-images
```

#### Create Signing Key

```bash
gcloud kms keyrings create living-content --location=global
gcloud kms keys create image-signer \
  --keyring=living-content \
  --location=global \
  --purpose=asymmetric-signing \
  --default-algorithm=ec-sign-p256-sha256
```

#### Set Permissions

```bash
# Incoming: developers can write, TM can read
gcloud artifacts repositories add-iam-policy-binding project-images-incoming \
  --location=us-central1 \
  --member="group:developers@livingcontent.co" \
  --role="roles/artifactregistry.writer"

# Trusted: only TM can write, clusters can read
gcloud artifacts repositories add-iam-policy-binding project-images \
  --location=us-central1 \
  --member="serviceAccount:tenant-manager@living-content.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
```

### 2. Tenant Manager Changes

#### Add Verify Endpoint

```python
# tenant-manager/app/api/routes/images.py
from fastapi import APIRouter, HTTPException
import subprocess

router = APIRouter(prefix="/api/images", tags=["images"])

@router.post("/verify-and-promote")
async def verify_and_promote(image: str, digest: str):
    # Verify signature
    result = subprocess.run([
        "cosign", "verify", 
        "--key", "gcpkms://projects/living-content/locations/global/keyRings/living-content/cryptoKeys/image-signer",
        f"{image}@{digest}"
    ], capture_output=True)
    
    if result.returncode != 0:
        raise HTTPException(400, "Invalid signature")
    
    # Promote to trusted
    source = f"{image}@{digest}"
    target = source.replace("project-images-incoming", "project-images")
    
    subprocess.run([
        "gcloud", "artifacts", "docker", "tags", "add",
        source, target
    ], check=True)
    
    return {"promoted": target, "digest": digest}
```

#### Update Image References

```python
# Use digests instead of tags
api_image = f"...project-images/stage-project-{project_id}-api@{digest}"
```

### 3. Build Process

#### Developer Workflow Script

```bash
#!/bin/bash
# build-and-promote.sh

PROJECT_ID=$1
COMPONENT=$2

# Build and push to incoming
IMAGE_IN="us-central1-docker.pkg.dev/living-content/project-images-incoming/stage-project-${PROJECT_ID}-${COMPONENT}:$(date +%s)"
docker build -f Dockerfile-${COMPONENT} -t "$IMAGE_IN" .
docker push "$IMAGE_IN"

# Get digest
DIGEST=$(docker inspect "$IMAGE_IN" --format='{{index .RepoDigests 0}}' | cut -d'@' -f2)

# Sign
cosign sign --key gcpkms://projects/living-content/locations/global/keyRings/living-content/cryptoKeys/image-signer \
  "${IMAGE_IN}@${DIGEST}"

# Request promotion
curl -X POST https://tenant-manager.stage/api/images/verify-and-promote \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"image\":\"$IMAGE_IN\",\"digest\":\"$DIGEST\"}"
```

### 4. Admission Control

#### Deploy Kyverno Policy

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: trusted-images-with-signature
spec:
  validationFailureAction: Enforce
  background: false
  rules:
    - name: enforce-trusted-repo-and-digest
      match:
        any:
        - resources:
            kinds: [Pod]
            namespaces: ["project-*"]
      validate:
        message: "Images must come from trusted registry and use digest pinning."
        pattern:
          spec:
            containers:
              - image: "us-central1-docker.pkg.dev/living-content/project-images/*@sha256:*"

    - name: verify-gcp-kms-signature
      match:
        any:
        - resources:
            kinds: [Pod]
            namespaces: ["project-*"]
      verifyImages:
        - imageReferences:
            - "us-central1-docker.pkg.dev/living-content/project-images/*"
          key: "gcpkms://projects/living-content/locations/global/keyRings/living-content/cryptoKeys/image-signer"
          attestations:
            - type: cosign
              predicateType: verification
              # Optional: enforce that the attestation came from Tenant Manager
              # by matching subject/issuer in the attestation payload if desired.
```

```bash
kubectl apply -f kyverno-policy.yaml
```

## TODO

- [ ] Deploy Tenant Manager with config routes
- [ ] Create incoming registry
- [ ] Create KMS signing key
- [ ] Add verify-and-promote endpoint
- [ ] Update build scripts
- [ ] Test signing flow
- [ ] Update lco-devops to use digests
- [ ] Deploy Kyverno policy
- [ ] End-to-end testing
- [ ] Update deployment documentation
- [ ] Production ready

## Testing

### Verify Current System Works

```bash
lco-devops project create --project-name test-security --tenant-ids 1
```

### Test New Flow

```bash
./build-and-promote.sh 123 api
kubectl get pods -n project-123 # Should run with verified image
```

## Configuration Storage

- **Secrets**: Remain in Google Secret Manager
- **Config**: Remains in Firestore
- **No changes** to existing config management

## What Changes for Developers

1. Push to `project-images-incoming` instead of `project-images`
2. Sign images after push
3. Request promotion via API
4. Use digests in deployments, not tags

## What Stays the Same

- Config management unchanged
- Secret management unchanged
- Deployment commands unchanged
- API interfaces unchanged
