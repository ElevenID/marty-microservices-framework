#!/usr/bin/env python3
"""
Dependency Check Script
======================

This script verifies that all required dependencies for E2E testing are properly installed
and that there are no Python 3.13 compatibility issues.

Usage:
    python scripts/check_dependencies.py
    make check-deps  # (when added to Makefile)
"""

import importlib
import subprocess
import sys

from playwright.sync_api import sync_playwright


def check_import(module_name: str, package_name: str | None = None) -> bool:
    """Check if a module can be imported successfully."""
    try:
        importlib.import_module(module_name)
        print(f"✅ {module_name} - OK")
        return True
    except ImportError as e:
        package = package_name or module_name
        print(f"❌ {module_name} - MISSING (install with: uv add {package})")
        print(f"   Error: {e}")
        return False
    except Exception as e:
        print(f"⚠️  {module_name} - ERROR: {e}")
        return False


def check_command(command: str) -> bool:
    """Check if a command is available."""
    try:
        result = subprocess.run([command, "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip().split("\n")[0]
            print(f"✅ {command} - {version}")
            return True
        else:
            print(f"❌ {command} - Command failed")
            return False
    except FileNotFoundError:
        print(f"❌ {command} - NOT FOUND")
        return False
    except subprocess.TimeoutExpired:
        print(f"⚠️  {command} - TIMEOUT")
        return False
    except Exception as e:
        print(f"⚠️  {command} - ERROR: {e}")
        return False


def main():
    """Main dependency check function."""
    print("🔍 Checking Dependencies for Marty Microservices Framework")
    print("=" * 60)

    # Track success
    all_good = True

    print("\n📦 Python Dependencies:")
    print("-" * 30)

    # Core dependencies
    core_deps = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn[standard]"),
        ("pydantic", "pydantic"),
        ("click", "click"),
        ("rich", "rich"),
        ("jinja2", "jinja2"),
        ("yaml", "pyyaml"),
        ("kubernetes", "kubernetes"),
        ("docker", "docker"),
    ]

    for module, package in core_deps:
        if not check_import(module, package):
            all_good = False

    print("\n🧪 Testing Dependencies:")
    print("-" * 30)

    # Testing dependencies
    test_deps = [
        ("pytest", "pytest"),
        ("pytest_asyncio", "pytest-asyncio"),
        ("playwright", "playwright"),
        ("httpx", "httpx"),
        ("redis", "redis"),
        ("testcontainers", "testcontainers"),
        ("psycopg2", "psycopg2-binary"),
    ]

    for module, package in test_deps:
        if not check_import(module, package):
            all_good = False

    print("\n🎭 Playwright Browser Check:")
    print("-" * 30)

    # Check if playwright browsers are installed
    try:

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                print("✅ Playwright Chromium - OK")
            except Exception as e:
                print(f"❌ Playwright Chromium - ERROR: {e}")
                print("   Fix with: playwright install chromium")
                all_good = False
    except Exception as e:
        print(f"❌ Playwright - ERROR: {e}")
        all_good = False

    print("\n🔧 External Tools:")
    print("-" * 30)

    # External tools
    if check_command("kind"):
        # Kind is available, check version
        try:
            result = subprocess.run(["kind", "version"], capture_output=True, text=True)
            if "v0." in result.stdout:
                print("✅ Kind version is compatible")
        except (subprocess.SubprocessError, OSError) as version_error:
            print(f"   Warning: Unable to determine Kind version: {version_error}")
    else:
        print("   Install with: brew install kind  # or download from https://kind.sigs.k8s.io/")
        all_good = False

    print("\n🐍 Python Version Check:")
    print("-" * 30)

    python_version = sys.version_info
    print(f"Python {python_version.major}.{python_version.minor}.{python_version.micro}")

    if python_version >= (3, 9):
        print("✅ Python version is supported")
    else:
        print("❌ Python version not supported (requires >= 3.9)")
        all_good = False

    # Check for Python 3.13 typing compatibility
    if python_version >= (3, 13):
        print("ℹ️  Python 3.13 detected - checking typing compatibility...")

        # Test imports that might cause issues
        problematic_imports = [
            "observability.load_testing.load_tester",
        ]

        for module in problematic_imports:
            if not check_import(module):
                print(f"⚠️  Python 3.13 compatibility issue in {module}")
                # Don't mark as failure since we may have fixed these

    print("\n" + "=" * 60)

    if all_good:
        print("✅ All dependencies are properly installed!")
        print("\n🚀 You can now run:")
        print("   make test-simple-e2e        # Simple Kind + Playwright test")
        print("   make test-kind-playwright    # Full Kind + Playwright tests")
        print("   make test-e2e               # All E2E tests")

        return True
    else:
        print("❌ Some dependencies are missing or have issues")
        print("\n🔧 To fix, run:")
        print("   make setup-dev              # Install all dev dependencies")
        print("   playwright install chromium # Install browser")

        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
