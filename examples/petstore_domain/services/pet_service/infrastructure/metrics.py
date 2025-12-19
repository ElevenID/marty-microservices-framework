"""Business Metrics for Pet Service.

This module defines custom business metrics for the pet service
using the MMF FrameworkMetrics helper.
"""

from mmf.framework.observability.framework_metrics import FrameworkMetrics


class PetMetrics(FrameworkMetrics):
    """Business metrics for the Pet Service.

    Provides custom metrics for tracking pet registration, catalog operations,
    and service performance.
    """

    def __init__(self) -> None:
        """Initialize pet service metrics."""
        super().__init__("pet_service")

        # Business metrics for pets
        self.pets_registered = self.create_counter(
            "pets_registered_total",
            "Total number of pets registered in the system",
            ["species"],
        )

        self.pets_deleted = self.create_counter(
            "pets_deleted_total",
            "Total number of pets deleted from the system",
            ["species"],
        )

        self.pets_retrieved = self.create_counter(
            "pets_retrieved_total",
            "Total number of pet retrieval requests",
            ["species"],
        )

        # Inventory metrics
        self.pets_by_species = self.create_gauge(
            "pets_by_species",
            "Number of pets currently in the system by species",
            ["species"],
        )

        self.total_pets = self.create_gauge(
            "total_pets",
            "Total number of pets currently in the system",
        )

        # Performance metrics
        self.list_pets_duration = self.create_histogram(
            "list_pets_duration_seconds",
            "Time to list all pets",
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
        )

    def record_pet_registered(self, species: str = "unknown") -> None:
        """Record a new pet registration."""
        if self.pets_registered:
            self.pets_registered.labels(
                species=species, service=self.service_name
            ).inc()

    def record_pet_deleted(self, species: str = "unknown") -> None:
        """Record a pet deletion."""
        if self.pets_deleted:
            self.pets_deleted.labels(
                species=species, service=self.service_name
            ).inc()

    def record_pet_retrieved(self, species: str = "unknown") -> None:
        """Record a pet retrieval."""
        if self.pets_retrieved:
            self.pets_retrieved.labels(
                species=species, service=self.service_name
            ).inc()

    def update_pets_by_species(self, species: str, count: int) -> None:
        """Update the count of pets for a given species."""
        if self.pets_by_species:
            self.pets_by_species.labels(
                species=species, service=self.service_name
            ).set(count)

    def update_total_pets(self, count: int) -> None:
        """Update the total pet count."""
        if self.total_pets:
            self.total_pets.labels(service=self.service_name).set(count)

    def record_list_pets_duration(self, duration_seconds: float) -> None:
        """Record the time taken to list all pets."""
        if self.list_pets_duration:
            self.list_pets_duration.labels(service=self.service_name).observe(
                duration_seconds
            )


# Singleton instance for the service
_metrics: PetMetrics | None = None


def get_pet_metrics() -> PetMetrics:
    """Get or create the pet metrics singleton.

    Returns:
        PetMetrics instance
    """
    global _metrics
    if _metrics is None:
        _metrics = PetMetrics()
    return _metrics
