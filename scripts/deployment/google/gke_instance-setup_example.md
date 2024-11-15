# GKE Cluster Setup and Management Example

This is to be used as a baseline example for Kubernetes deployment. It is not a guide; it is not complete.

## Project Creation

1. **Set the project:**

   ```bash
   gcloud config set project living-content
   ```

2. **Describe the static IP address:**

   ```bash
   gcloud compute addresses describe living-content-static-ip --global
   ```

3. **Create a firewall rule to allow HTTPS:**

   ```bash
   gcloud compute firewall-rules create allow-https \
     --network default \
     --direction INGRESS \
     --action ALLOW \
     --rules tcp:443 \
     --source-ranges 0.0.0.0/0
   ```

## Cluster Creation

**Create a GKE cluster:**

```bash
gcloud container clusters create living-content-{environment} \
  --region us-central1 \
  --machine-type t2a-standard-1 \
  --num-nodes=2 \
  --disk-size=80GB
```

## Namespace and Repository Setup

1. **Create a Kubernetes namespace:**

   ```bash
   kubectl create namespace {project_name}
   ```

2. **Create an artifact repository:**

   ```bash
   gcloud artifacts repositories create {project_name} --repository-format=docker --location=us-central1
   ```

3. **Tag and push Docker images:**

   ```bash
   docker tag living-content-{project_name}-api:{environment} us-central1-docker.pkg.dev/living-content/{project_name}/api:{environment}
   docker push us-central1-docker.pkg.dev/living-content/{project_name}/api:{environment}

   docker tag living-content-{project_name}-mongo:{environment} us-central1-docker.pkg.dev/living-content/{project_name}/mongo:{environment}
   docker push us-central1-docker.pkg.dev/living-content/{project_name}/mongo:{environment}

   docker tag living-content-{project_name}-redis:{environment} us-central1-docker.pkg.dev/living-content/{project_name}/redis:{environment}
   docker push us-central1-docker.pkg.dev/living-content/{project_name}/redis:{environment}
   ```

4. **Generate GKE secrets:**

   ```bash
   python ./scripts/deployment/google/generate_gke_secrets.py ./secrets/{environment}/secrets.yaml --namespace {project_name}
   ```

## Certificate Manager Setup

1. **Create DNS authorizations:**

   ```bash
   gcloud certificate-manager dns-authorizations create {project_name}-api{-environment} \
     --domain="api.{project_name}{-environment}.livingcontent.co"

   gcloud certificate-manager dns-authorizations create {project_name}{-environment} \
     --domain="{project_name}{-environment}.livingcontent.co"
   ```

## Kubernetes Deployment Steps

### Step 1: Apply Managed Certificate

```bash
kubectl apply -f ./deployment/google/{environment}/managed-cert.yaml
```

### Step 2: Apply PersistentVolumeClaims

```bash
kubectl apply -f ./deployment/google/{environment}/api-logs-persistentvolumeclaim.yaml
kubectl apply -f ./deployment/google/{environment}/mongo-config-persistentvolumeclaim.yaml
kubectl apply -f ./deployment/google/{environment}/mongo-db-persistentvolumeclaim.yaml
kubectl apply -f ./deployment/google/{environment}/mongo-logs-persistentvolumeclaim.yaml
kubectl apply -f ./deployment/google/{environment}/redis-db-persistentvolumeclaim.yaml
```

### Step 3: Apply Deployments

```bash
kubectl apply -f ./deployment/google/{environment}/api-deployment.yaml
kubectl apply -f ./deployment/google/{environment}/mongo-deployment.yaml
kubectl apply -f ./deployment/google/{environment}/redis-deployment.yaml
```

### Step 4: Apply Services

```bash
kubectl apply -f ./deployment/google/{environment}/api-service.yaml
kubectl apply -f ./deployment/google/{environment}/mongo-service.yaml
kubectl apply -f ./deployment/google/{environment}/redis-service.yaml
```

### Step 5: Apply Backendconfig and Ingress

```bash
kubectl apply -f ./deployment/google/{environment}/api-backendconfig.yaml
kubectl apply -f ./deployment/google/{environment}/api-ingress.yaml
```

## Common Kubernetes Commands

### Pod Management

- **List all pods:**

  ```bash
  kubectl get pods -n {project_name} -o wide
  ```

- **Describe a pod:**

  ```bash
  kubectl describe pod {pod_id} -n {project_name} -o wide
  ```

- **Delete a pod:**

  ```bash
  kubectl delete pod {pod_id} -n {project_name}
  ```

- **Delete all pods:**

  ```bash
  kubectl delete pods --all -n {project_name}
  ```

- **Roll out updates:**

  ```bash
  kubectl rollout restart deployment/api -n {project_name}
  ```

### Secrets Management

- **List all secrets:**

  ```bash
  kubectl get secrets -n {project_name}
  ```

- **Delete a secret:**

  ```bash
  kubectl delete secret {secret_name} -n {namespace}
  ```

### DNS Authorization Management

- **List all DNS authorizations:**

  ```bash
  gcloud certificate-manager dns-authorizations list
  ```

- **Describe a DNS authorization:**

  ```bash
  gcloud certificate-manager dns-authorizations describe {project_name}-api{-environment}
  ```

### Pod Access

- **SSH into a pod:**

  ```bash
  kubectl exec -it {pod_id} -n {project_name} -- /bin/sh
  ```

### Log Management

- **Follow logs (since 1 second ago):**

  ```bash
  kubectl logs -f -l app=api -n {project_name} --since=1s
  ```

- **Tail the last 100 entries:**

  ```bash
  kubectl logs --tail=100 {pod_id} -n {project_name}
  ```

### Context Management

- **Get cluster contexts:**

  ```bash
  kubectl config get-contexts
  ```

- **Change context:**

  ```bash
  kubectl config use-context {context_name}
  ```
