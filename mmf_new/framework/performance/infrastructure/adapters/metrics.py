"""
System Metrics Infrastructure Adapters.
"""

from datetime import datetime, timezone

import psutil

from mmf_new.framework.performance.domain.entities import ResourceMetrics
from mmf_new.framework.performance.domain.ports import MetricsProviderPort


class SystemMetricsAdapter(MetricsProviderPort):
    """Metrics provider implementation using psutil."""

    def get_current_metrics(self) -> ResourceMetrics:
        """Get current system resource metrics."""
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk_io = psutil.disk_io_counters()
        net_io = psutil.net_io_counters()

        # Handle cases where io counters might be None (e.g. some environments)
        disk_read = disk_io.read_bytes if disk_io else 0
        disk_write = disk_io.write_bytes if disk_io else 0
        net_sent = net_io.bytes_sent if net_io else 0
        net_recv = net_io.bytes_recv if net_io else 0

        return ResourceMetrics(
            timestamp=datetime.now(timezone.utc),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_available=memory.available,
            disk_io_read=disk_read,
            disk_io_write=disk_write,
            network_bytes_sent=net_sent,
            network_bytes_recv=net_recv,
            process_count=len(psutil.pids()),
            thread_count=self._get_thread_count(),
        )

    def _get_thread_count(self) -> int:
        """Get total thread count for the current process."""
        try:
            p = psutil.Process()
            return p.num_threads()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0
