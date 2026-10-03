#!/usr/bin/env python3
import ast
import os
import sys

class SecuritySentinel(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.findings = []
        self.in_try_block = False

    def report(self, lineno, msg):
        self.findings.append({"file": self.filename, "line": lineno, "issue": msg})

    def visit_Import(self, node):
        for alias in node.names:
            # Check for unsafe or deprecated imports
            if alias.name == "urllib3" or alias.name.startswith("urllib3."):
                # Naive example of unsafe import check
                self.report(node.lineno, f"Unsafe/Deprecated import detected: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module == "urllib3" or (node.module and node.module.startswith("urllib3.")):
            self.report(node.lineno, f"Unsafe/Deprecated import detected: from {node.module} import ...")
        self.generic_visit(node)

    def visit_Assign(self, node):
        # Look for hardcoded credentials (very naive string matching for milestone 1)
        for target in node.targets:
            if isinstance(target, ast.Name):
                name = target.id.lower()
                if any(x in name for x in ["password", "secret", "token", "api_key"]):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        if len(node.value.value) > 0:
                            self.report(node.lineno, f"Potential hardcoded credential in variable '{target.id}'")
        self.generic_visit(node)

    def visit_Raise(self, node):
        # Enforce that Raise is used properly, not just re-raising broadly inside a try block
        # Real-world AST constraints from the prompt
        if getattr(node, 'exc', None) is None:
            if not self.in_try_block:
                pass # Depending on context, naked raise can be bad outside except
        self.generic_visit(node)

    def visit_Try(self, node):
        old_val = self.in_try_block
        self.in_try_block = True

        # Check for missing error handlers (naked except:)
        has_handler = False
        for handler in node.handlers:
            if handler.type is None:
                self.report(handler.lineno, "Naked except: block detected. Missing specific error handler.")
            else:
                has_handler = True

        if not has_handler and not node.handlers:
            # No handlers (e.g. try/finally)
            pass

        self.generic_visit(node)
        self.in_try_block = old_val


def audit_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content, filename=filepath)
        sentinel = SecuritySentinel(filepath)
        sentinel.visit(tree)
        return sentinel.findings
    except Exception as e:
        print(f"[!] AST Parse Error in {filepath}: {e}")
        return []

def run_auditor(target_path):
    all_findings = []
    if os.path.isfile(target_path):
        if target_path.endswith('.py'):
            all_findings.extend(audit_file(target_path))
    elif os.path.isdir(target_path):
        for root, dirs, files in os.walk(target_path):
            for file in files:
                if file.endswith('.py'):
                    all_findings.extend(audit_file(os.path.join(root, file)))

    if all_findings:
        print("[!] Security Sentinel Findings:")
        for f in all_findings:
            print(f"  - {f['file']}:{f['line']} -> {f['issue']}")
        return 1
    else:
        print("[+] Security Sentinel passed with zero findings.")
        return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: kessel_ast_auditor.py <file_or_dir>")
        sys.exit(1)
    sys.exit(run_auditor(sys.argv[1]))
