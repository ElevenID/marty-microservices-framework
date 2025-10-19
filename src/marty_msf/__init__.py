"""
Marty Microservices Framework (MSF)

A comprehensive microservices framework for building scalable, distributed applications.
"""

from .framework.events import BaseEvent, EnhancedEventBus, EventBus, EventMetadata

__version__ = "1.0.0"
__author__ = "Marty Framework Team"
__email__ = "team@marty-msf.com"

# Import the Enhanced Event Bus for convenient top-level access

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    # Primary event system - easy access from top level
    "EnhancedEventBus",
    "EventBus",
    "BaseEvent",
    "EventMetadata",
]
