#!/usr/bin/env python3
"""
Test script for external connectors package imports
"""

import os
import sys
import traceback

from marty_msf.framework.integration.external_connectors.base import (
    ExternalSystemConnector,
)
from marty_msf.framework.integration.external_connectors.config import (
    ExternalSystemConfig,
)
from marty_msf.framework.integration.external_connectors.enums import ConnectorType

# Add the project root to the Python path
project_root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
sys.path.insert(0, project_root)

try:
    # Test direct module imports

    print("✅ All relative imports working correctly!")
    print(f"✅ ConnectorType: {ConnectorType.REST_API}")
    print(f"✅ Available connector types: {list(ConnectorType)}")
    print("✅ ExternalSystemConfig available")
    print("✅ ExternalSystemConnector base class available")

except ImportError as e:
    print(f"❌ Import error: {e}")

    traceback.print_exc()
    sys.exit(1)
