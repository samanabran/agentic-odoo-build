"""
Eval harness runner (H1).

Discovers task_*.py files in eval/tasks/, runs each, and prints a summary.
Exit code 0 if all executed tasks pass (skips are not failures).
Exit code 1 if any task fails.

Usage:
    cd orchestrator && python -m eval.runner
    cd orchestrator && python -m eval.runner --filter task_002
"""

import importlib
import sys
from pathlib import Path

# Windows cp1252 can't encode arrow/emoji characters used in task messages.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Load .env from project root so eval tasks see all required env vars without
# the caller having to source the file manually.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env", override=False)
except ImportError:
    pass


def run_all(filter_prefix: str = "") -> None:
    tasks_dir = Path(__file__).parent / "tasks"
    task_files = sorted(f for f in tasks_dir.glob("task_*.py") if f.stem != "__init__")

    if filter_prefix:
        task_files = [f for f in task_files if filter_prefix in f.stem]

    results: list[tuple[str, str, str]] = []  # (name, status, message)

    for task_file in task_files:
        module_name = f"eval.tasks.{task_file.stem}"
        try:
            mod = importlib.import_module(module_name)
            passed, skipped, message = mod.run()
            status = "SKIP" if skipped else ("PASS" if passed else "FAIL")
        except Exception as exc:
            status = "FAIL"
            message = f"runner error: {exc}"

        results.append((task_file.stem, status, message))

    # Print summary table
    print()
    print("  Eval harness results")
    print("  " + "-" * 60)
    for name, status, message in results:
        pad = " " * max(0, 35 - len(name))
        print(f"  [{status}] {name}{pad}{message}")
    print("  " + "-" * 60)

    n_pass = sum(1 for _, s, _ in results if s == "PASS")
    n_skip = sum(1 for _, s, _ in results if s == "SKIP")
    n_fail = sum(1 for _, s, _ in results if s == "FAIL")
    print(f"  {n_pass} passed  {n_skip} skipped  {n_fail} failed")
    print()

    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    filter_arg = ""
    if len(sys.argv) == 3 and sys.argv[1] == "--filter":
        filter_arg = sys.argv[2]
    run_all(filter_arg)
