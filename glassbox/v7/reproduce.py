# SPDX-License-Identifier: BUSL-1.1
# Copyright (C) 2026 Ajay Pravin Mahale <mahale.ajay01@gmail.com>
# Licensed under the Business Source License 1.1 (see LICENSE-COMMERCIAL).
# Free for non-production use and for production use inside your own organisation.
# Offering it as a commercial service or product to third parties needs a license.
"""Reproduce a V7 experiment from its evidence package (V7 Hard Gate 5 tooling).

Two commands:

* ``plan <package>`` verifies the package and prints the exact steps: check out the
  commit whose code produced the results, set up the pinned environment, re-run, and
  compare. The steps come from ``experiments/v7/reproduce_recipes.json``.
* ``compare <package> <fresh results.json ...>`` verifies the package again and compares
  the fresh results with the packaged ones. It writes a reproduction report that names
  the reproducer and their environment. It never overwrites a report.

Verdicts:

* ``REPRODUCED``: every non-float value (verdicts, pass flags, counts, labels) is
  identical, and every float is within ``tol``;
* ``DECISIONS_ONLY``: every non-float value is identical, but some float differs by
  more than ``tol``;
* ``NOT_REPRODUCED``: any non-float value differs, or a key is missing or added.

A report by the author in another environment is a same-author reproduction. Only a
report by an independent person can support the ``REPRODUCED`` status in ASSURANCE.md.

Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from glassbox.v7.evidence import verify_package

PathLike = Union[str, Path]
REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / "experiments" / "v7" / "reproduce_recipes.json"


class ReproductionError(RuntimeError):
    """Raised when a package fails verification or has no usable recipe."""


def load_recipes(path: PathLike = RECIPES) -> Dict[str, Dict[str, Any]]:
    """Recipes keyed by package id (the ``_about`` entry is dropped)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _walk(
    a: Any,
    b: Any,
    path: str,
    tol: float,
    ignore: Sequence[str],
    out: List[Dict[str, Any]],
) -> None:
    if path in ignore:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            sub = f"{path}.{key}" if path else str(key)
            if key not in a or key not in b:
                if sub not in ignore:
                    out.append(
                        {"path": sub, "kind": "missing", "a": key in a, "b": key in b}
                    )
                continue
            _walk(a[key], b[key], sub, tol, ignore, out)
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append({"path": path, "kind": "length", "a": len(a), "b": len(b)})
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _walk(x, y, f"{path}[{i}]", tol, ignore, out)
        return
    if _is_num(a) and _is_num(b) and (isinstance(a, float) or isinstance(b, float)):
        if abs(a - b) > tol:
            out.append({"path": path, "kind": "float", "a": a, "b": b})
        return
    if a != b or type(a) is not type(b):
        out.append({"path": path, "kind": "value", "a": a, "b": b})


def compare_results(
    original: Any, fresh: Any, tol: float = 1e-4, ignore: Sequence[str] = ()
) -> Dict[str, Any]:
    """Compare two results documents; see the module docstring for the verdicts."""
    mismatches: List[Dict[str, Any]] = []
    _walk(original, fresh, "", tol, tuple(ignore), mismatches)
    if not mismatches:
        verdict = "REPRODUCED"
    elif all(m["kind"] == "float" for m in mismatches):
        verdict = "DECISIONS_ONLY"
    else:
        verdict = "NOT_REPRODUCED"
    return {
        "verdict": verdict,
        "tol": tol,
        "ignore": list(ignore),
        "mismatches": mismatches,
    }


def _verified(package: PathLike) -> Path:
    pkg = Path(package)
    problems = verify_package(pkg)
    if problems:
        raise ReproductionError(f"{pkg} fails verification: {problems[:3]}")
    return pkg


def _recipe(pkg: Path, recipe: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if recipe is not None:
        return recipe
    recipes = load_recipes()
    if pkg.name not in recipes:
        raise ReproductionError(f"no recipe for {pkg.name} in {RECIPES}")
    return recipes[pkg.name]


def plan(package: PathLike, recipe: Optional[Dict[str, Any]] = None) -> str:
    """Human-readable reproduction steps for a verified package."""
    pkg = _verified(package)
    r = _recipe(pkg, recipe)
    lines = [
        f"Reproduce {pkg.name}",
        f"Expected run time: {r.get('runtime', 'not stated')}",
        "",
        "1. Get the code that produced the packaged results:",
        "   git clone https://github.com/designer-coderajay/glassbox-mech.git",
        "   cd glassbox-mech",
        f"   git checkout {r['commit']}",
        "2. Set up the environment:",
        *[f"   {c}" for c in r["setup"]],
        "3. Re-run (writes to repro/, never to the committed results):",
        *[f"   {c}" for c in r["run"]],
        "4. Compare, from a checkout of the current main branch with its environment:",
        f"   python -m glassbox.v7.reproduce compare evidence/{pkg.name} "
        + " ".join(f"<checkout>/{p}" for p in r["results"])
        + ' --reproducer "Your Name" --out reproduction_report.json',
    ]
    if r.get("notes"):
        lines += ["", f"Note: {r['notes']}"]
    return "\n".join(lines) + "\n"


def _manifest_sha(pkg: Path) -> str:
    return hashlib.sha256((pkg / "manifest.json").read_bytes()).hexdigest()


def check(
    package: PathLike,
    fresh: Sequence[PathLike],
    out: PathLike,
    reproducer: str,
    environment: str,
    recipe: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compare fresh results with the packaged ones and write a report (never overwrites).

    Raises:
        ReproductionError: If the package fails verification or the file counts differ.
        FileExistsError: If ``out`` exists.
    """
    target = Path(out)
    if target.exists():
        raise FileExistsError(f"{target} exists; reports are never overwritten")
    pkg = _verified(package)
    r = _recipe(pkg, recipe)
    packaged = [pkg / "artifacts" / rel for rel in r["packaged_results"]]
    if len(packaged) != len(fresh):
        raise ReproductionError(
            f"expected {len(packaged)} results files, got {len(fresh)}"
        )
    parts = []
    for orig_path, fresh_path in zip(packaged, fresh):
        a = json.loads(orig_path.read_text(encoding="utf-8"))
        b = json.loads(Path(fresh_path).read_text(encoding="utf-8"))
        cmp = compare_results(a, b, float(r.get("tol", 1e-4)), r.get("ignore", ()))
        parts.append({"packaged": str(orig_path.relative_to(pkg)), **cmp})
    order = ["REPRODUCED", "DECISIONS_ONLY", "NOT_REPRODUCED"]
    verdict = max((p["verdict"] for p in parts), key=order.index)
    report = {
        "package": pkg.name,
        "package_manifest_sha256": _manifest_sha(pkg),
        "recipe_commit": r.get("commit"),
        "reproducer": reproducer,
        "environment": environment,
        "checker_platform": platform.platform(),
        "verdict": verdict,
        "parts": parts,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(report, indent=1) + "\n")
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI: ``plan <package>`` or ``compare <package> <results...> --reproducer ...``."""
    parser = argparse.ArgumentParser(description="Reproduce a V7 evidence package")
    sub = parser.add_subparsers(dest="command", required=True)
    p_plan = sub.add_parser("plan")
    p_plan.add_argument("package", type=Path)
    p_cmp = sub.add_parser("compare")
    p_cmp.add_argument("package", type=Path)
    p_cmp.add_argument("results", nargs="+", type=Path)
    p_cmp.add_argument("--reproducer", required=True)
    p_cmp.add_argument("--environment", default=platform.platform())
    p_cmp.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "plan":
        sys.stdout.write(plan(args.package))
        return 0
    rep = check(args.package, args.results, args.out, args.reproducer, args.environment)
    for part in rep["parts"]:
        sys.stdout.write(f"{part['packaged']}: {part['verdict']}\n")
        for m in part["mismatches"][:20]:
            sys.stdout.write(
                f"   {m['kind']} {m['path']}: {m.get('a')} -> {m.get('b')}\n"
            )
    sys.stdout.write(f"VERDICT: {rep['verdict']}  (report: {args.out})\n")
    return 0 if rep["verdict"] == "REPRODUCED" else 1


if __name__ == "__main__":
    sys.exit(main())
