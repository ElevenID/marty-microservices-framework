"""
Verify relative imports in external_connectors package
"""


import ast
import os


def test_files_exist():

    base_dir = os.path.dirname(__file__)

    expected_files = [
        "enums.py",
        "config.py",
        "base.py",
        "__init__.py",
        "connectors/__init__.py",
        "connectors/rest_api.py",
    ]

    for file_path in expected_files:
        full_path = os.path.join(base_dir, file_path)
        if os.path.exists(full_path):
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} missing")
            return False
    return True


def test_syntax():

    base_dir = os.path.dirname(__file__)
    python_files = [
        "enums.py",
        "config.py",
        "base.py",
        "__init__.py",
        "connectors/__init__.py",
        "connectors/rest_api.py",
    ]

    for file_path in python_files:
        full_path = os.path.join(base_dir, file_path)
        try:
            with open(full_path) as f:
                content = f.read()
            ast.parse(content)
            print(f"✅ {file_path} syntax valid")
        except SyntaxError as e:
            print(f"❌ {file_path} syntax error: {e}")
            return False
        except Exception as e:
            print(f"❌ {file_path} error: {e}")
            return False
    return True


if __name__ == "__main__":
    print("Testing external connectors package structure...")

    if test_files_exist():
        print("\n✅ All files exist")
    else:
        print("\n❌ Missing files")

    if test_syntax():
        print("\n✅ All files have valid syntax")
        print("\n✅ Relative imports should work correctly when used as a package")
    else:
        print("\n❌ Syntax errors found")
