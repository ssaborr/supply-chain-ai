#!/usr/bin/env python3
"""
====================================================================
DevSecOps Local Security Auditor & Gate Runner
Smart Supply Chain AI Dashboard (ssaborr/supply-chain-ai)
====================================================================
This utility executes the core Shift-Left DevSecOps pipeline locally:
  1. Bandit (Python SAST - Static Application Security Testing)
  2. pip-audit (Python SCA - Software Composition Analysis)
  3. Pytest + MLSecOps Guardrails Quality Gate
  4. npm audit (Angular Frontend Dependency Security)
====================================================================
"""

import os
import sys
import subprocess

GREEN = "\033[92m" if os.name != "nt" else ""
RED = "\033[91m" if os.name != "nt" else ""
YELLOW = "\033[93m" if os.name != "nt" else ""
CYAN = "\033[96m" if os.name != "nt" else ""
BOLD = "\033[1m" if os.name != "nt" else ""
RESET = "\033[0m" if os.name != "nt" else ""

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "BackEnd")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "FrontEnd")

# Resolve python / venv binaries
VENV_PYTHON = (
    os.path.join(BACKEND_DIR, "venv", "Scripts", "python.exe")
    if os.name == "nt"
    else os.path.join(BACKEND_DIR, "venv", "bin", "python")
)
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable

VENV_BANDIT = (
    os.path.join(BACKEND_DIR, "venv", "Scripts", "bandit.exe")
    if os.name == "nt"
    else os.path.join(BACKEND_DIR, "venv", "bin", "bandit")
)
VENV_PIPAUDIT = (
    os.path.join(BACKEND_DIR, "venv", "Scripts", "pip-audit.exe")
    if os.name == "nt"
    else os.path.join(BACKEND_DIR, "venv", "bin", "pip-audit")
)


def run_command(title: str, cmd: list, cwd: str) -> bool:
    print("\n" + "=" * 68)
    print(f"[DevSecOps Gate] {title}")
    print(f"Command:     {' '.join(cmd)}")
    print(f"Working Dir: {cwd}")
    print("=" * 68)

    try:
        proc = subprocess.run(cmd, cwd=cwd)
        if proc.returncode == 0:
            print(f"--> [PASSED] {title}")
            return True
        else:
            print(f"--> [COMPLETED WITH FINDINGS / EXIT CODE {proc.returncode}] {title}")
            return False
    except FileNotFoundError as e:
        print(f"--> [SKIPPED / NOT FOUND] {title}: {e}")
        return False


def main():
    print("=" * 68)
    print("  DevSecOps & MLSecOps Local Security Pipeline Runner")
    print("  Smart Supply Chain AI Platform")
    print("=" * 68)

    results = {}

    # Gate 1: Python SAST (Bandit)
    if os.path.exists(VENV_BANDIT):
        bandit_cmd = [VENV_BANDIT, "-r", "app", "-ll", "-f", "screen"]  # -ll reports Medium and High severity
        results["FastAPI SAST (Bandit)"] = run_command("Python SAST Code Scan (Bandit)", bandit_cmd, BACKEND_DIR)
    else:
        results["FastAPI SAST (Bandit)"] = False

    # Gate 2: Python SCA (pip-audit)
    if os.path.exists(VENV_PIPAUDIT):
        # Ignore PYSEC-2026-1325: known transitive advisory in ecdsa with no upstream fix yet
        pip_cmd = [VENV_PIPAUDIT, "-r", "requirements.txt", "--ignore-vuln", "PYSEC-2026-1325"]
        results["Python Dependencies (pip-audit)"] = run_command("Python SCA Dependency Scan", pip_cmd, BACKEND_DIR)
    else:
        results["Python Dependencies (pip-audit)"] = False

    # Gate 3: Pytest & MLSecOps Guardrails Quality Gate
    test_cmd = [VENV_PYTHON, "-m", "pytest", "tests", "-v"]
    results["Backend Tests & MLSecOps Guardrails"] = run_command("Pytest & MLSecOps Guardrails Test Suite", test_cmd, BACKEND_DIR)

    # Gate 4: Frontend SCA (npm audit)
    npm_bin = "npm.cmd" if os.name == "nt" else "npm"
    npm_cmd = [npm_bin, "audit", "--audit-level=critical"]
    results["Frontend Dependencies (npm audit)"] = run_command("Angular SCA Dependency Scan", npm_cmd, FRONTEND_DIR)

    # Summary
    print("\n" + "=" * 68)
    print("DevSecOps Pipeline Execution Summary:")
    print("=" * 68)
    all_passed = True
    for gate, passed in results.items():
        status = "PASSED" if passed else "CHECK FINDINGS"
        if not passed:
            all_passed = False
        print(f" * {gate:45} : {status}")

    print("=" * 68)
    if all_passed:
        print("ALL DEVSECOPS QUALITY GATES PASSED! Ready for deployment.\n")
    else:
        print("Review findings above for your PFE security audit documentation.\n")


if __name__ == "__main__":
    main()
