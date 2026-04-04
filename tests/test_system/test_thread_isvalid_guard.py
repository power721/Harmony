from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = ("services", "ui")
SKIP_DIRS = {"__pycache__"}
CONTEXT_WINDOW = 3
IS_RUNNING_PATTERN = re.compile(r"(?P<obj>[A-Za-z_][\w\.]*)\.isRunning\(")


def _iter_python_files():
    for scan_dir in SCAN_DIRS:
        base_dir = PROJECT_ROOT / scan_dir
        for path in base_dir.rglob("*.py"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            yield path


def test_is_running_calls_are_guarded_by_is_valid():
    violations = []

    for path in _iter_python_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines, start=1):
            if ".isRunning(" not in line or line.lstrip().startswith("#"):
                continue

            context_start = max(0, index - CONTEXT_WINDOW - 1)
            context = re.sub(r"\s+", "", "\n".join(lines[context_start:index]))
            for match in IS_RUNNING_PATTERN.finditer(line):
                obj_name = match.group("obj")
                guard_text = f"isValid({obj_name})"
                if guard_text not in context:
                    rel_path = path.relative_to(PROJECT_ROOT)
                    violations.append(f"{rel_path}:{index} -> {line.strip()}")

    assert not violations, (
        "Found thread `.isRunning()` calls without an `isValid(...)` guard:\n"
        + "\n".join(violations)
    )
