#!/usr/bin/env python3
"""
Setup script for Marty CLI development environment.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description, cwd=None):
    """Run a command and handle errors."""
    print(f"🔄 {description}...")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=cwd)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"   Command: {cmd}")
        print(f"   Exit code: {e.returncode}")
        if e.stdout:
            print(f"   STDOUT: {e.stdout}")
        if e.stderr:
            print(f"   STDERR: {e.stderr}")
        return False


def main():
    """Main setup function."""
    print("🚀 Marty CLI Development Setup")
    print("=" * 40)

    framework_path = Path(__file__).parent
    print(f"📁 Working in: {framework_path}")

    # Check if we're in a virtual environment
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )

    if not in_venv:
        print("⚠️  Warning: Not in a virtual environment")
        print("   Consider creating one with: python3 -m venv venv && source venv/bin/activate")

    print(f"🐍 Using Python: {sys.executable}")

    # Install the package in development mode
    steps = [
        (
            ["uv", "sync", "--group", "dev"],
            "Installing Marty CLI with uv (dev dependencies)",
        ),
        (
            ["uv", "add", "--dev", "pytest", "pytest-json-report"],
            "Adding test dependencies",
        ),
        (
            ["uv", "pip", "install", "-e", "."],
            "Installing CLI in development mode",
        ),
    ]

    failed_steps = []
    for cmd, description in steps:
        if not run_command(cmd, description, cwd=framework_path):
            failed_steps.append(description)

    print("\n" + "=" * 40)
    print("📊 Setup Results")
    print("=" * 40)

    if failed_steps:
        print(f"❌ {len(failed_steps)} step(s) failed:")
        for step in failed_steps:
            print(f"   - {step}")
        print("\n💡 Try running setup manually:")
        print("   uv sync --group dev")
        print("   uv add --dev pytest pytest-json-report")
        print("   uv pip install -e .")
        return 1
    print("✅ All setup steps completed successfully!")
    print("\n🎉 Ready to use Marty CLI!")
    print("\nNext steps:")
    print("   1. Run tests: python3 scripts/test_runner.py")
    print("   2. Try CLI: marty --help")
    print("   3. Create a service: marty new fastapi-service my-service")
    return 0


if __name__ == "__main__":
    sys.exit(main())
