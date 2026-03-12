#!/usr/bin/env python3
"""
Validate all Python files in workspace to detect corruption early.
Run as: python3 scripts/validate_python_files.py
"""

import sys
import os
import py_compile

def validate_directory(root):
    errors = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden dirs and __pycache__
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '__pycache__']
        for f in filenames:
            if f.endswith('.py'):
                path = os.path.join(dirpath, f)
                try:
                    py_compile.compile(path, doraise=True)
                except py_compile.PyCompileError as e:
                    errors.append((path, str(e)))
    return errors

if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    errors = validate_directory(root)
    if errors:
        print("❌ Python syntax errors detected:")
        for path, err in errors:
            print(f"  {path}: {err}")
        sys.exit(1)
    else:
        print("✅ All Python files valid")
        sys.exit(0)
