"""Truth / Belief Firewall Test (Spec §5.4 item 3).

Walks the AST of all modules under `samanvay` to verify that `samanvay.core.truth`
is NEVER imported by any module other than `samanvay.sim` and `samanvay.eval`.
"""

import ast
import os
from pathlib import Path


ALLOWED_TRUTH_PREFIXES = (
    "samanvay.sim",
    "samanvay.eval",
    "samanvay.core.truth",
)


def get_module_name_from_path(root_dir: Path, file_path: Path) -> str:
    """Compute dotted Python module name from file path relative to root."""
    rel = file_path.relative_to(root_dir)
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def test_truth_belief_firewall():
    """Verify that samanvay.core.truth is strictly isolated behind the firewall."""
    repo_root = Path(__file__).resolve().parent.parent
    samanvay_dir = repo_root / "samanvay"
    assert samanvay_dir.exists(), f"Directory not found: {samanvay_dir}"

    violations: list[str] = []

    for root, _, files in os.walk(samanvay_dir):
        for file in files:
            if not file.endswith(".py"):
                continue

            file_path = Path(root) / file
            mod_name = get_module_name_from_path(repo_root, file_path)

            # Check if this module is allowed to import truth
            is_allowed = any(mod_name == p or mod_name.startswith(p + ".") for p in ALLOWED_TRUTH_PREFIXES)

            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read(), filename=str(file_path))
                except SyntaxError as e:
                    violations.append(f"Syntax error in {file_path}: {e}")
                    continue

            for node in ast.walk(tree):
                # import samanvay.core.truth
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "truth" in alias.name and not is_allowed:
                            violations.append(
                                f"FIREWALL VIOLATION: {mod_name} ({file_path}:{node.lineno}) imports '{alias.name}'"
                            )
                # from samanvay.core import truth / from samanvay.core.truth import ...
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if "truth" in module and not is_allowed:
                        violations.append(
                            f"FIREWALL VIOLATION: {mod_name} ({file_path}:{node.lineno}) imports from '{module}'"
                        )
                    elif module.endswith("core"):
                        for alias in node.names:
                            if alias.name == "truth" and not is_allowed:
                                violations.append(
                                    f"FIREWALL VIOLATION: {mod_name} ({file_path}:{node.lineno}) imports 'truth' from '{module}'"
                                )

    assert not violations, "\n".join(violations)


def test_workstream_isolation():
    """Verify that workstream packages w1...w6 import only core, never each other (§5.4 item 2)."""
    repo_root = Path(__file__).resolve().parent.parent
    samanvay_dir = repo_root / "samanvay"
    violations: list[str] = []

    workstreams = ["w1", "w2", "w3", "w4", "w5", "w6"]

    for ws in workstreams:
        ws_dir = samanvay_dir / ws
        if not ws_dir.exists():
            continue

        for root, _, files in os.walk(ws_dir):
            for file in files:
                if not file.endswith(".py"):
                    continue

                file_path = Path(root) / file
                mod_name = get_module_name_from_path(repo_root, file_path)

                with open(file_path, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=str(file_path))

                for node in ast.walk(tree):
                    imported_modules = []
                    if isinstance(node, ast.Import):
                        imported_modules = [a.name for a in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported_modules = [node.module]

                    for imp in imported_modules:
                        for other_ws in workstreams:
                            if other_ws != ws and f"samanvay.{other_ws}" in imp:
                                violations.append(
                                    f"WORKSTREAM ISOLATION VIOLATION: {mod_name} ({file_path}:{node.lineno}) imports '{imp}'"
                                )

    assert not violations, "\n".join(violations)
