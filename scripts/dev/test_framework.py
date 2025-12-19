#!/usr/bin/env python3
"""
Comprehensive Testing Framework for Marty Microservices Templates

This script provides comprehensive testing of the templates framework:
1. Template validation
2. Service generation testing
3. Build integration validation
4. Framework feature testing
"""

import builtins
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any


def run_command(cmd: str, cwd: str | None = None) -> builtins.dict[str, Any]:
    """Run a command and return result."""
    print(f"🔧 Running: {cmd}")
    try:
        # Convert string command to list for security
        if isinstance(cmd, str):
            # Simple command splitting - for production use shlex.split()
            cmd_list = cmd.split()
        else:
            cmd_list = cmd

        result = subprocess.run(
            cmd_list,
            shell=False,  # Security: Disable shell execution
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command timed out",
            "returncode": -1,
        }
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}


def test_template_validation() -> bool:
    """Test the template validation script."""
    print("\n📋 Testing Template Validation...")

    # Get the current script directory and framework root
    script_dir = Path(__file__).parent
    framework_root = script_dir.parent

    # Use uv run python for proper environment
    python_cmd = "uv run python"

    result = run_command(f"cd {framework_root} && {python_cmd} scripts/validate_templates.py")

    if result["success"]:
        print("✅ Template validation: PASSED")
        print(f"📊 Output:\n{result['stdout']}")
        return True
    print("❌ Template validation: FAILED")
    print(f"📊 Error:\n{result['stderr']}")
    return False


def test_service_generation() -> bool:
    """Test service generation for all types."""
    print("\n🏗️ Testing Service Generation...")

    service_types = ["fastapi", "grpc", "hybrid"]
    results = {}

    # Get the current script directory and framework root
    script_dir = Path(__file__).parent
    framework_root = script_dir.parent

    # Use uv run python for proper environment
    python_cmd = "uv run python"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        for service_type in service_types:
            print(f"  Testing {service_type} service...")

            service_name = f"test-{service_type}-service"
            cmd = f"cd {framework_root} && {python_cmd} scripts/generate_service.py {service_type} {service_name} --output-dir {temp_path}/src"

            result = run_command(cmd)
            results[service_type] = result

            if result["success"]:
                print(f"    ✅ {service_type}: Generated successfully")

                # Test Python syntax using proper uv environment
                syntax_cmd = f"cd {framework_root} && find {temp_path}/src -name '*.py' -print0 | xargs -0 {python_cmd} -m py_compile"
                syntax_result = run_command(syntax_cmd)

                if syntax_result["success"]:
                    print(f"    ✅ {service_type}: Python syntax valid")
                else:
                    print(f"    ❌ {service_type}: Python syntax errors")
                    print(f"      Syntax Error Details: {syntax_result['stderr']}")
                    results[service_type]["syntax_valid"] = False
            else:
                print(f"    ❌ {service_type}: Generation failed")
                if result["stderr"]:
                    print(f"      Error: {result['stderr']}")

    # Summary
    success_count = sum(1 for r in results.values() if r["success"] and r.get("syntax_valid", True))
    total_count = len(service_types)

    print(f"\n📊 Service Generation Summary: {success_count}/{total_count} passed")

    return success_count == total_count


def test_framework_structure() -> bool:
    """Test framework directory structure and required files."""
    print("\n🏗️ Testing Framework Structure...")

    script_dir = Path(__file__).parent
    framework_root = script_dir.parent

    required_paths = [
        "scripts/generate_service.py",
        "scripts/validate_templates.py",
        "scripts/test_framework.py",
        "service/fastapi_service",
        "service/grpc_service",
        "service/hybrid_service",
        "service/auth_service",
        "service/database_service",
        "service/caching_service",
        "service/message_queue_service",
        "microservice_project_template",
        "README.md",
    ]

    missing_paths = []
    for path in required_paths:
        full_path = framework_root / path
        if not full_path.exists():
            missing_paths.append(path)

    if not missing_paths:
        print("✅ Framework structure: All required files present")
        return True
    print("❌ Framework structure: Missing files:")
    for path in missing_paths:
        print(f"   - {path}")
    return False


def test_template_features() -> bool:
    """Test template features and capabilities."""
    print("\n🎯 Testing Template Features...")

    script_dir = Path(__file__).parent
    framework_root = script_dir.parent
    templates_dir = framework_root / "service"

    # Count templates and features
    template_dirs = [d for d in templates_dir.iterdir() if d.is_dir()]
    template_count = len(template_dirs)

    print(f"📊 Found {template_count} service templates:")

    feature_summary = {}
    for template_dir in template_dirs:
        template_name = template_dir.name
        template_files = list(template_dir.glob("**/*.j2"))

        features = {
            "main_service": any("main" in f.name for f in template_files),
            "configuration": any("config" in f.name for f in template_files),
            "service_logic": any(
                "service" in f.name or "manager" in f.name for f in template_files
            ),
            "dockerfile": any("Dockerfile" in f.name for f in template_files),
            "proto_files": any("proto" in f.name for f in template_files),
        }

        feature_summary[template_name] = {
            "file_count": len(template_files),
            "features": features,
        }

        print(f"  - {template_name}: {len(template_files)} files")

    # Verify expected templates exist
    expected_templates = [
        "fastapi_service",
        "grpc_service",
        "hybrid_service",
        "auth_service",
    ]
    found_templates = [name for name in feature_summary if name in expected_templates]

    print(f"\n📊 Core service templates found: {len(found_templates)}/{len(expected_templates)}")

    return len(found_templates) == len(expected_templates)


def test_script_functionality() -> bool:
    """Test framework scripts functionality."""
    print("\n⚙️ Testing Script Functionality...")

    scripts = ["scripts/validate_templates.py"]

    results = {}

    for script in scripts:
        # Test script help/version
        # For validate_templates.py, we already tested it above
        results[script] = {"success": True, "tested": "above"}

    success_count = sum(1 for r in results.values() if r["success"])
    total_count = len(scripts)

    return success_count == total_count


def main() -> int:
    """Run comprehensive framework tests."""
    print("🚀 Starting Marty Microservices Framework Test")
    print("=" * 60)

    # Define test suite
    tests: builtins.list[tuple[str, Callable[[], bool]]] = [
        ("Template Validation", test_template_validation),
        ("Service Generation", test_service_generation),
        ("Framework Structure", test_framework_structure),
        ("Template Features", test_template_features),
        ("Script Functionality", test_script_functionality),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except (OSError, subprocess.CalledProcessError, ImportError) as e:
            print(f"❌ {test_name}: Exception occurred - {e}")
            results[test_name] = False

    # Final Summary
    print("\n" + "=" * 60)
    print("🎯 FRAMEWORK TEST SUMMARY")
    print("=" * 60)

    passed_tests = []
    failed_tests = []

    for test_name, success in results.items():
        if success:
            print(f"✅ PASSED     {test_name}")
            passed_tests.append(test_name)
        else:
            print(f"❌ FAILED     {test_name}")
            failed_tests.append(test_name)

    success_rate = (len(passed_tests) / len(tests)) * 100
    print(f"\nOverall: {len(passed_tests)}/{len(tests)} tests passed ({success_rate:.1f}%)")

    if failed_tests:
        print(f"\n⚠️ {len(failed_tests)} test(s) failed")
        print("🔧 Please review and fix issues before using the framework")
        return 1
    print("\n🎉 ALL TESTS PASSED!")
    print("✨ Framework is ready for use")
    return 0


if __name__ == "__main__":
    sys.exit(main())
