import time

import pytest
from kubernetes import client, config
from kubernetes.client.rest import ApiException


@pytest.mark.e2e
@pytest.mark.scaling
def test_service_scaling():
    """
    Test scaling of the identity-service deployment.
    Verifies that the service can be scaled up and down.
    """
    try:
        # Try loading kubeconfig (local) or in-cluster config
        try:
            config.load_kube_config()
        except config.ConfigException:
            config.load_incluster_config()
    except Exception:
        pytest.skip("Kubernetes configuration not found, skipping scaling test")

    apps_v1 = client.AppsV1Api()
    deployment_name = "identity-service"
    namespace = "mmf-system"

    # Check if deployment exists
    try:
        deployment = apps_v1.read_namespaced_deployment(deployment_name, namespace)
    except ApiException as e:
        if e.status == 404:
            pytest.skip(f"Deployment {deployment_name} not found in namespace {namespace}")
        raise

    # Scale up
    original_replicas = deployment.spec.replicas or 1
    target_replicas = original_replicas + 1

    print(f"Scaling {deployment_name} from {original_replicas} to {target_replicas}")

    patch = {"spec": {"replicas": target_replicas}}
    apps_v1.patch_namespaced_deployment(deployment_name, namespace, patch)

    # Wait for scale up
    timeout = 120
    start_time = time.time()
    scaled_up = False
    while time.time() - start_time < timeout:
        dep = apps_v1.read_namespaced_deployment(deployment_name, namespace)
        if dep.status.ready_replicas == target_replicas:
            scaled_up = True
            break
        time.sleep(2)

    if not scaled_up:
        # Revert before failing
        patch = {"spec": {"replicas": original_replicas}}
        apps_v1.patch_namespaced_deployment(deployment_name, namespace, patch)
        pytest.fail(f"Timeout waiting for {deployment_name} to scale to {target_replicas}")

    # Scale down
    print(f"Scaling {deployment_name} back to {original_replicas}")
    patch = {"spec": {"replicas": original_replicas}}
    apps_v1.patch_namespaced_deployment(deployment_name, namespace, patch)

    # Wait for scale down
    start_time = time.time()
    while time.time() - start_time < timeout:
        dep = apps_v1.read_namespaced_deployment(deployment_name, namespace)
        if dep.status.ready_replicas == original_replicas:
            break
        time.sleep(2)
    else:
        pytest.fail(f"Timeout waiting for {deployment_name} to scale back to {original_replicas}")
