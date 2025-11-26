"""
Chaos Engineering Test Configuration

This module provides pytest configuration and fixtures for chaos engineering tests.
Chaos tests validate system resilience, fault tolerance, and recovery capabilities.
"""

import asyncio
import random
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any

import pytest
import requests


class ChaosType(Enum):
    """Types of chaos engineering experiments."""

    NETWORK_PARTITION = "network_partition"
    POD_FAILURE = "pod_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    LATENCY_INJECTION = "latency_injection"
    SERVICE_UNAVAILABLE = "service_unavailable"
    DATA_CORRUPTION = "data_corruption"


@dataclass
class ChaosExperiment:
    """Container for chaos experiment configuration."""

    name: str
    chaos_type: ChaosType
    target: str
    duration: int  # seconds
    intensity: float  # 0.0 to 1.0
    recovery_time: int  # seconds
    success_criteria: dict[str, Any]


@pytest.fixture
def chaos_config():
    """Configuration for chaos engineering experiments."""
    return {
        "target_namespace": "mmf-system",
        "target_service": "identity-service",
        "experiment_duration": 60,  # seconds
        "recovery_timeout": 300,  # seconds
        "health_check_interval": 5,  # seconds
        "success_threshold": 0.95,  # 95% success rate
        "max_response_time": 5.0,  # seconds
    }


@pytest.fixture
def kubernetes_chaos():
    """Provides Kubernetes-specific chaos engineering capabilities."""

    def kill_random_pod(namespace: str, label_selector: str) -> str:
        """Kill a random pod matching the label selector."""
        try:
            # Get pods
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", namespace, "-l", label_selector, "-o", "name"],
                capture_output=True,
                text=True,
                check=True,
            )

            pods = result.stdout.strip().split("\n")
            if not pods or pods == [""]:
                return "No pods found"

            # Kill random pod
            target_pod = random.choice(pods)
            subprocess.run(["kubectl", "delete", "-n", namespace, target_pod], check=True)

            return f"Killed {target_pod}"
        except subprocess.CalledProcessError as e:
            return f"Error: {e}"

    def create_network_partition(namespace: str, service: str) -> str:
        """Create network partition using NetworkPolicy."""
        network_policy = f"""
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: chaos-network-partition
  namespace: {namespace}
spec:
  podSelector:
    matchLabels:
      app: {service}
  policyTypes:
  - Ingress
  - Egress
  ingress: []
  egress: []
"""
        try:
            proc = subprocess.Popen(
                ["kubectl", "apply", "-f", "-"], stdin=subprocess.PIPE, text=True
            )
            proc.communicate(input=network_policy)
            return "Network partition created"
        except Exception as e:
            return f"Error creating network partition: {e}"

    def remove_network_partition(namespace: str) -> str:
        """Remove network partition."""
        try:
            subprocess.run(
                ["kubectl", "delete", "networkpolicy", "chaos-network-partition", "-n", namespace],
                check=True,
            )
            return "Network partition removed"
        except subprocess.CalledProcessError:
            return "Network partition not found or already removed"

    def inject_cpu_stress(namespace: str, pod_name: str, duration: int) -> str:
        """Inject CPU stress into a pod."""
        stress_command = f"stress --cpu 4 --timeout {duration}s"
        try:
            subprocess.run(
                ["kubectl", "exec", "-n", namespace, pod_name, "--", "sh", "-c", stress_command],
                check=True,
            )
            return f"CPU stress injected into {pod_name}"
        except subprocess.CalledProcessError as e:
            return f"Error injecting CPU stress: {e}"

    return {
        "kill_pod": kill_random_pod,
        "create_network_partition": create_network_partition,
        "remove_network_partition": remove_network_partition,
        "inject_cpu_stress": inject_cpu_stress,
    }


@pytest.fixture
def chaos_monitor():
    """Provides monitoring capabilities during chaos experiments."""

    def monitor_service_health(service_url: str, duration: int, interval: int = 5):
        """Monitor service health during chaos experiment."""

        start_time = time.time()
        end_time = start_time + duration
        results = []

        while time.time() < end_time:
            try:
                response = requests.get(f"{service_url}/health", timeout=10)
                results.append(
                    {
                        "timestamp": time.time(),
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds(),
                        "success": response.status_code == 200,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "timestamp": time.time(),
                        "status_code": None,
                        "response_time": None,
                        "success": False,
                        "error": str(e),
                    }
                )

            time.sleep(interval)

        # Calculate metrics
        total_requests = len(results)
        successful_requests = sum(1 for r in results if r["success"])
        success_rate = successful_requests / total_requests if total_requests > 0 else 0

        response_times = [r["response_time"] for r in results if r["response_time"]]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "success_rate": success_rate,
            "avg_response_time": avg_response_time,
            "results": results,
        }

    return {"monitor_health": monitor_service_health}


@pytest.fixture
def fault_injection():
    """Provides fault injection capabilities."""

    @contextmanager
    def inject_latency(delay_ms: int):
        """Inject artificial latency."""
        original_sleep = time.sleep

        def delayed_sleep(duration):
            original_sleep(duration + delay_ms / 1000)

        time.sleep = delayed_sleep
        try:
            yield
        finally:
            time.sleep = original_sleep

    @contextmanager
    def inject_errors(error_rate: float):
        """Inject random errors."""
        original_get = requests.get
        original_post = requests.post

        def error_get(*args, **kwargs):
            if random.random() < error_rate:
                raise requests.exceptions.ConnectionError("Chaos-injected error")
            return original_get(*args, **kwargs)

        def error_post(*args, **kwargs):
            if random.random() < error_rate:
                raise requests.exceptions.ConnectionError("Chaos-injected error")
            return original_post(*args, **kwargs)

        requests.get = error_get
        requests.post = error_post
        try:
            yield
        finally:
            requests.get = original_get
            requests.post = original_post

    return {"inject_latency": inject_latency, "inject_errors": inject_errors}


@pytest.fixture
def resilience_patterns():
    """Provides resilience pattern testing utilities."""

    def test_circuit_breaker(service_call, failure_threshold: int = 5):
        """Test circuit breaker pattern."""
        failure_count = 0
        circuit_open = False

        def circuit_breaker_call():
            nonlocal failure_count, circuit_open

            if circuit_open:
                raise Exception("Circuit breaker is open")

            try:
                result = service_call()
                failure_count = 0  # Reset on success
                return result
            except Exception:
                failure_count += 1
                if failure_count >= failure_threshold:
                    circuit_open = True
                raise

        return circuit_breaker_call

    def test_retry_with_backoff(service_call, max_retries: int = 3, backoff_factor: float = 2.0):
        """Test retry with exponential backoff."""

        def retry_call():
            for attempt in range(max_retries + 1):
                try:
                    return service_call()
                except Exception as e:
                    if attempt == max_retries:
                        raise e
                    time.sleep(backoff_factor**attempt)

        return retry_call

    def test_bulkhead_isolation(service_calls: list, isolation_limit: int = 3):
        """Test bulkhead isolation pattern."""

        def isolated_calls():
            with ThreadPoolExecutor(max_workers=isolation_limit) as executor:
                futures = [executor.submit(call) for call in service_calls]
                results = []
                for future in futures:
                    try:
                        results.append(future.result(timeout=10))
                    except Exception as e:
                        results.append(f"Error: {e}")
                return results

        return isolated_calls

    return {
        "circuit_breaker": test_circuit_breaker,
        "retry_with_backoff": test_retry_with_backoff,
        "bulkhead_isolation": test_bulkhead_isolation,
    }


@dataclass
class RequestResult:
    status: str = "success"


class SystemUnderTest:
    """Simulated system under test."""

    def __init__(self):
        self.network_partition_active = False
        self.latency_ms = 0
        self.packet_loss_rate = 0.0
        self.memory_pressure_level = 0.0
        self.cpu_stress_load = 0.0
        self.disk_latency_ms = 0
        self.disk_full_percent = 0.0
        self.disk_error_rate = 0.0
        self.failed_dependencies = set()
        self.traffic_spike_active = False

    async def make_request(self):
        """Simulate a request."""
        if self.network_partition_active:
            raise ConnectionError("Network partition")
        
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000)
            
        if random.random() < self.packet_loss_rate:
            raise ConnectionError("Packet loss")

        if self.failed_dependencies:
            if "database" in self.failed_dependencies:
                return RequestResult(status="degraded")
            if "message_queue" in self.failed_dependencies:
                return RequestResult(status="degraded")
            return RequestResult(status="success")

        await asyncio.sleep(0.01)
        return RequestResult(status="success")

    async def perform_disk_operation(self):
        """Simulate disk operation."""
        if self.disk_error_rate > 0 and random.random() < self.disk_error_rate:
            raise IOError("Disk error")
        if self.disk_latency_ms > 0:
            await asyncio.sleep(self.disk_latency_ms / 1000)
        return True


@pytest.fixture
def system_under_test():
    """Provides a system under test."""
    return SystemUnderTest()


@dataclass
class ChaosExperimentRunner:
    """Runner for chaos experiments."""
    
    system: SystemUnderTest

    @asynccontextmanager
    async def network_partition(self):
        self.system.network_partition_active = True
        try:
            yield
        finally:
            self.system.network_partition_active = False

    @asynccontextmanager
    async def network_latency(self, latency_ms: int):
        self.system.latency_ms = latency_ms
        try:
            yield
        finally:
            self.system.latency_ms = 0

    @asynccontextmanager
    async def packet_loss(self, loss_rate: float):
        self.system.packet_loss_rate = loss_rate
        try:
            yield
        finally:
            self.system.packet_loss_rate = 0.0

    @asynccontextmanager
    async def memory_pressure(self, pressure_level: float):
        self.system.memory_pressure_level = pressure_level
        try:
            yield
        finally:
            self.system.memory_pressure_level = 0.0

    @asynccontextmanager
    async def cpu_stress(self, cpu_load: float):
        self.system.cpu_stress_load = cpu_load
        try:
            yield
        finally:
            self.system.cpu_stress_load = 0.0

    @asynccontextmanager
    async def slow_disk_io(self, latency_ms: int):
        self.system.disk_latency_ms = latency_ms
        try:
            yield
        finally:
            self.system.disk_latency_ms = 0

    @asynccontextmanager
    async def disk_full(self, usage_percent: float):
        self.system.disk_full_percent = usage_percent
        try:
            yield
        finally:
            self.system.disk_full_percent = 0.0

    @asynccontextmanager
    async def disk_io_errors(self, error_rate: float):
        self.system.disk_error_rate = error_rate
        try:
            yield
        finally:
            self.system.disk_error_rate = 0.0

    @asynccontextmanager
    async def service_failure(self, dependency: str):
        self.system.failed_dependencies.add(dependency)
        try:
            yield
        finally:
            self.system.failed_dependencies.remove(dependency)

    @asynccontextmanager
    async def multiple_service_failures(self, failed_services: list[str]):
        self.system.failed_dependencies.update(failed_services)
        try:
            yield
        finally:
            for s in failed_services:
                self.system.failed_dependencies.discard(s)

    @asynccontextmanager
    async def traffic_spike(self, spike_rps: int, spike_duration: int):
        self.system.traffic_spike_active = True
        try:
            yield
        finally:
            self.system.traffic_spike_active = False


@pytest.fixture
def chaos_experiment(system_under_test):
    """Provides chaos experiment capabilities."""
    return ChaosExperimentRunner(system_under_test)


@dataclass
class HealthStatus:
    """System health status."""
    overall_health: float = 1.0


class KubernetesCluster:
    """Simulated Kubernetes cluster."""

    async def get_pods(self, exclude_critical: bool = True) -> list[str]:
        """Get list of pods."""
        return ["pod-1", "pod-2", "pod-3"]

    async def terminate_pod(self, pod_name: str):
        """Terminate a pod."""
        pass

    async def check_system_health(self) -> HealthStatus:
        """Check system health."""
        return HealthStatus()


@pytest.fixture
def kubernetes_cluster():
    """Provides a simulated Kubernetes cluster."""
    return KubernetesCluster()


# Chaos engineering test markers
pytest.mark.chaos = pytest.mark.chaos
pytest.mark.fault_injection = pytest.mark.fault_injection
pytest.mark.resilience = pytest.mark.resilience
pytest.mark.recovery = pytest.mark.recovery
pytest.mark.network_chaos = pytest.mark.network_chaos
pytest.mark.resource_chaos = pytest.mark.resource_chaos
