# Import Order Check

This pre-commit hook ensures that all Python imports are placed at the top of files, after docstrings and comments but before any other code. **It now supports automatic fixing of import placement issues.**

## Features

- **Detection**: Identifies imports that come after function definitions, class definitions, or other executable code
- **Auto-fixing**: Can automatically move misplaced imports to the proper location at the top of files
- **Pre-commit Integration**: Runs as the **first** pre-commit check to ensure clean import placement
- **Flexible Execution**: Can be run manually with various options

## What it checks

- All `import` and `from ... import` statements are at the top of the file
- Imports come after module docstrings and initial comments
- No imports are scattered throughout the file after function/class definitions

## Examples

### ✅ Good (imports at top)
```python
#!/usr/bin/env python3
"""
Module docstring.
"""

import os
import sys
from typing import Any

def my_function():
    return os.getcwd()
```

### ❌ Bad (imports scattered)
```python
#!/usr/bin/env python3
"""
Module docstring.
"""

import os

def my_function():
    import sys  # ❌ Import after function definition
    return sys.version

import json  # ❌ Import after code
```

## Configuration

The check is configured in `.pre-commit-config.yaml`:

```yaml
- id: check-import-order
  name: Check Import Placement
  entry: python3 scripts/check_import_order.py
  language: system
  files: \.py$
  exclude: ^(tests/.*_test\.py|examples/.*\.py|scripts/detect_globals\.py|.*migration.*\.py|.*legacy.*\.py)$
  require_serial: true
  pass_filenames: false
  stages: [pre-commit]
```

## Script usage

The script can be run manually:

```bash
# Check specific files
python3 scripts/check_import_order.py file1.py file2.py

# Check directories
python3 scripts/check_import_order.py src/

# Check with exclusions
python3 scripts/check_import_order.py src/ --exclude=test --exclude=example

# Check all Python files in current directory
python3 scripts/check_import_order.py .
```

## Exit codes

- `0`: All files pass the import order check
- `1`: One or more files have import placement issues

## Rationale

Keeping imports at the top of files:

1. **Readability**: Makes dependencies immediately visible
2. **Performance**: Avoids repeated import overhead in loops/functions
3. **Standards compliance**: Follows PEP 8 guidelines
4. **Tool compatibility**: Works better with IDEs and static analysis tools
5. **Maintainability**: Easier to track and manage dependencies

## Exceptions handled

The checker properly handles:

- Shebang lines (`#!/usr/bin/env python3`)
- Encoding declarations (`# -*- coding: utf-8 -*-`)
- Module docstrings (triple-quoted strings at module level)
- Initial comments and blank lines
- Function-local imports are flagged as violations (they should be at module level)

## Integration with other tools

This check works alongside:

- `isort`: For sorting import order
- `ruff`: For import-related linting rules
- `mypy`: For type checking imports

The import order check focuses specifically on placement (top of file), while other tools handle sorting and style.
