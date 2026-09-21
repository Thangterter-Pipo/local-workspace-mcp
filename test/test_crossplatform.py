#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-Platform Test Suite for Local Workspace MCP.
Verifies:
  1. AST Syntax parsing for all Python files in the repository.
  2. Path normalization for Windows and POSIX environments (via _os_name).
  3. Drive / root discovery (get_roots) execution without crash.
  4. Command lookup (which_command) execution without crash.
  5. Environment variable security redaction (get_environment).
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from security.paths import PathError, normalize  # noqa: E402
from extended_tools import get_roots, which_command, get_environment  # noqa: E402


def test_ast_syntax() -> int:
    """Scan Python files and verify the canonical product identity/config."""
    print("\n--- [1/5] Testing AST Syntax for all Python files ---")
    checked_count = 0
    errors = []

    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Exclude virtual environments and caches
        dirs[:] = [d for d in dirs if d not in {".venv", "venv", "__pycache__", ".git", ".pytest_cache"}]
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                rel_path = file_path.relative_to(PROJECT_ROOT)
                checked_count += 1
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        source = f.read()
                    ast.parse(source, filename=str(file_path))
                    print(f"  [PASS] {rel_path}")
                except Exception as e:
                    print(f"  [FAIL] {rel_path}: {e}")
                    errors.append((rel_path, str(e)))

    if errors:
        print(f"AST Check Failed with {len(errors)} error(s)!")
        for p, err in errors:
            print(f"  - {p}: {err}")
        return 1

    server_source = (PROJECT_ROOT / "server.py").read_text(encoding="utf-8")
    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    identity_checks = {
        'FastMCP name="local-workspace"': 'name="local-workspace"' in server_source,
        "new environment prefix": "WORKSPACE_MCP_API_KEY" in server_source,
        "legacy environment fallback": "WORKSPACE_MCP_API_KEY" in server_source,
        "Windows runtime directory": '"LocalWorkspaceMCP"' in server_source,
        "POSIX runtime directory": '".local_workspace_mcp"' in server_source,
        "documented connector name": "Local Workspace" in env_example,
    }
    failed_identity = [name for name, ok in identity_checks.items() if not ok]
    if failed_identity:
        for name in failed_identity:
            print(f"  [FAIL] Identity/config: {name}")
        return 1
    for name in identity_checks:
        print(f"  [PASS] Identity/config: {name}")

    print(f"AST Check Passed: {checked_count} file(s) parsed successfully.")
    return 0


def test_path_normalization() -> int:
    """Test normalize() for both Windows and POSIX targets."""
    print("\n--- [2/5] Testing Path Normalization (Windows & POSIX) ---")
    passed = 0
    failed = 0

    # 1. Windows: normal path with dot-dot resolution
    try:
        res = normalize(r"C:\Users\test\..\test\project", _os_name="nt")
        assert "C:" in str(res) and "project" in str(res), f"Unexpected result: {res}"
        print(f"  [PASS] Windows dot-dot resolution -> {res}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Windows dot-dot resolution: {e}")
        failed += 1

    # 2. Windows: reserved device names
    try:
        normalize(r"C:\CON.txt", _os_name="nt")
        print("  [FAIL] Windows reserved name CON.txt did not raise PathError")
        failed += 1
    except PathError as e:
        assert e.code == "INVALID_PATH"
        print(f"  [PASS] Windows reserved name rejected ({e.message})")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Windows reserved name raised unexpected: {e}")
        failed += 1

    # 3. Windows / POSIX: empty path & NUL byte rejection
    try:
        normalize("", _os_name="nt")
        print("  [FAIL] Empty path did not raise PathError")
        failed += 1
    except PathError:
        print("  [PASS] Empty path rejected")
        passed += 1

    try:
        normalize("C:\\bad\x00path", _os_name="nt")
        print("  [FAIL] NUL byte did not raise PathError")
        failed += 1
    except PathError:
        print("  [PASS] NUL byte rejected")
        passed += 1

    # 4. POSIX: absolute path normalization & dot-dot resolution
    try:
        posix_res = normalize("/Users/alice/projects/../repos/myproject", _os_name="posix")
        assert str(posix_res) == "/Users/alice/repos/myproject", f"Unexpected POSIX result: {posix_res}"
        print(f"  [PASS] POSIX dot-dot resolution -> {posix_res}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] POSIX dot-dot resolution: {e}")
        failed += 1

    # 5. POSIX: relative path resolution against cwd (e.g. "." or subpaths)
    try:
        posix_rel = normalize(".", _os_name="posix")
        expected_cwd = Path.cwd().as_posix()
        assert expected_cwd in str(posix_rel) or str(posix_rel) == expected_cwd, f"Unexpected POSIX relative result: {posix_rel}"
        print(f"  [PASS] POSIX relative path '.' resolved -> {posix_rel}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] POSIX relative path '.': {e}")
        failed += 1

    try:
        posix_rel_sub = normalize("sub/dir", _os_name="posix")
        assert "sub/dir" in str(posix_rel_sub), f"Unexpected POSIX relative subpath result: {posix_rel_sub}"
        print(f"  [PASS] POSIX relative path 'sub/dir' resolved -> {posix_rel_sub}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] POSIX relative path 'sub/dir': {e}")
        failed += 1

    print(f"Path Normalization Tests: {passed} passed, {failed} failed.")
    return 1 if failed > 0 else 0


def test_get_roots_execution() -> int:
    """Test get_roots() executes cleanly without crashing."""
    print("\n--- [3/5] Testing get_roots() Execution ---")
    try:
        result = get_roots()
        assert isinstance(result, dict), "get_roots() must return a dict"
        assert result.get("success") is True, f"get_roots() failed: {result}"
        roots = result.get("roots", [])
        assert isinstance(roots, list), "result['roots'] must be a list"
        print(f"  [PASS] get_roots() returned {len(roots)} root(s):")
        for r in roots:
            drive_or_path = r.get("drive") or r.get("path")
            size_info = r.get("total_human", "N/A")
            print(f"    - {drive_or_path} (Total: {size_info}, Type: {r.get('type', 'unknown')})")
        return 0
    except Exception as e:
        print(f"  [FAIL] get_roots() crashed: {e}")
        return 1


def test_which_command_execution() -> int:
    """Test which_command() executes cleanly for both existing and missing commands."""
    print("\n--- [4/5] Testing which_command() Execution ---")
    passed = 0
    failed = 0

    # 1. Existing command (python)
    try:
        res = which_command("python")
        assert isinstance(res, dict)
        assert res.get("success") is True
        assert res.get("found") is True
        print(f"  [PASS] which_command('python') -> found: {res.get('path')} (source: {res.get('source')})")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] which_command('python'): {e}")
        failed += 1

    # 2. Missing command (random string)
    try:
        res = which_command("nonexistent_command_xyz_12345")
        assert isinstance(res, dict)
        assert res.get("success") is True
        assert res.get("found") is False
        assert res.get("path") is None
        print(f"  [PASS] which_command('nonexistent_command_xyz_12345') -> correctly returned found=False")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] which_command('nonexistent_command_xyz_12345'): {e}")
        failed += 1

    print(f"which_command Tests: {passed} passed, {failed} failed.")
    return 1 if failed > 0 else 0


def test_get_environment_security() -> int:
    """Test get_environment() redacts sensitive variables properly."""
    print("\n--- [5/5] Testing get_environment() Security Redaction ---")
    import os
    os.environ["TEST_SECRET_KEY"] = "super_secret_123"
    os.environ["MY_PASSWORD"] = "pass_456"
    os.environ["UNSAFE_TOKEN"] = "token_789"
    os.environ["PUBLIC_VAR"] = "public_value"

    try:
        res = get_environment(names="TEST_SECRET_KEY,MY_PASSWORD,UNSAFE_TOKEN,PUBLIC_VAR,NONEXISTENT")
        assert res.get("success") is True, f"Failed: {res}"
        values = res.get("values", {})
        assert values.get("TEST_SECRET_KEY") == "<redacted>", f"Secret key not redacted: {values}"
        assert values.get("MY_PASSWORD") == "<redacted>", f"Password not redacted: {values}"
        assert values.get("UNSAFE_TOKEN") == "<redacted>", f"Token not redacted: {values}"
        assert values.get("PUBLIC_VAR") == "public_value", f"Public var corrupted: {values}"
        assert values.get("NONEXISTENT") is None, f"Nonexistent var should be None: {values}"
        print("  [PASS] get_environment correctly redacts sensitive keywords (KEY, PASSWORD, TOKEN)")
        return 0
    except Exception as e:
        print(f"  [FAIL] get_environment security test failed: {e}")
        return 1
    finally:
        os.environ.pop("TEST_SECRET_KEY", None)
        os.environ.pop("MY_PASSWORD", None)
        os.environ.pop("UNSAFE_TOKEN", None)
        os.environ.pop("PUBLIC_VAR", None)


def main() -> int:
    print("=======================================================")
    print(" Local Workspace MCP - Cross-Platform Automated Tests")
    print(f" Python Interpreter: {sys.executable}")
    print(f" Operating System:   {os.name} ({sys.platform})")
    print("=======================================================")

    results = [
        test_ast_syntax(),
        test_path_normalization(),
        test_get_roots_execution(),
        test_which_command_execution(),
        test_get_environment_security(),
    ]

    total_failures = sum(results)
    print("\n=======================================================")
    if total_failures == 0:
        print(" ALL CROSS-PLATFORM TESTS PASSED SUCCESSFULLY! (5/5)")
    else:
        print(f" TEST SUITE FAILED WITH {total_failures} SUITE FAILURE(S)!")
    print("=======================================================")
    return 1 if total_failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
