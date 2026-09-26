#!/usr/bin/env python3
import ast
import sys
import os
import subprocess

def scan_file(filepath):
    try:
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read(), filename=filepath)
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return False

    # Basic security checks: exec/eval
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', '') in ('eval', 'exec'):
            print(f"SECURITY ALERT: Found {node.func.id} in {filepath}")
            return False
    return True

def main():
    # Only scan staged python files
    result = subprocess.run(['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'], capture_output=True, text=True)
    staged_files = [f for f in result.stdout.splitlines() if f.endswith('.py')]

    all_passed = True
    for f in staged_files:
        # Prevent directory traversal - only scan files inside repo that exist
        if os.path.isfile(f) and not f.startswith('../') and not f.startswith('/'):
            if not scan_file(f):
                all_passed = False

    if not all_passed:
        sys.exit(1)

if __name__ == '__main__':
    main()
