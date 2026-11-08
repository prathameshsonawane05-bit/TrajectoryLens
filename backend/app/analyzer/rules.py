import re
from difflib import SequenceMatcher

from app.analyzer.registry import Finding, Severity, registered_rules, rule
from app.models import Run, Step

# A later command joins an earlier loop when it is at most this many steps after
# the previous repeat. A gap of 5 covers both commands inside a 6-step window.
_WINDOW_GAP = 5
_OUTPUT_SIMILARITY = 0.9
_PATH_RE = re.compile(r"(?<![\w.-])([\w.-]+(?:/[\w.-]+)*\.[A-Za-z0-9]+)")
_EXCEPTION_RE = re.compile(r"\b([A-Za-z]+(?:Error|Exception))\b")


def _ordered(run: Run) -> list[Step]:
    return sorted(run.steps, key=lambda step: step.index)


def _canonical_file(path: str) -> str:
    cleaned = path.strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def _is_absolute(path: str) -> bool:
    return path.startswith("/") or (len(path) >= 3 and path[1] == ":" and path[2] == "/")


def _is_bare(path: str) -> bool:
    return "/" not in path


def _directory_suffix_match(left: str, right: str) -> bool:
    """Absolute and relative paths with a directory, when one ends with the other."""
    if not left or not right or left == right:
        return False
    if _is_absolute(left) == _is_absolute(right):
        return False
    longer, shorter = (left, right) if len(left) >= len(right) else (right, left)
    if _is_bare(shorter):
        return False
    return longer.endswith("/" + shorter)


def _group_roots(canonical: list[str]) -> list[int]:
    """Cluster paths. A bare filename joins only a single candidate path."""
    parent = list(range(len(canonical)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left_index, left in enumerate(canonical):
        for right_index in range(left_index + 1, len(canonical)):
            right = canonical[right_index]
            if left == right or _directory_suffix_match(left, right):
                union(left_index, right_index)

    for index, name in enumerate(canonical):
        if not name or not _is_bare(name):
            continue
        candidates: set[int] = set()
        for other_index, other in enumerate(canonical):
            if other_index == index or not other or _is_bare(other):
                continue
            if other.endswith("/" + name):
                candidates.add(find(other_index))
        if len(candidates) == 1:
            union(index, next(iter(candidates)))
    return [find(index) for index in range(len(canonical))]


def _group_key(path: str, cohort: list[str]) -> str:
    paths = [*cohort, path]
    canonical = [_canonical_file(item) for item in paths]
    roots = _group_roots(canonical)
    root = roots[-1]
    members = [name for name, found in zip(canonical, roots, strict=True) if found == root and name]
    return min(members) if members else canonical[-1]


def _normalize_command(text: str) -> str:
    """Drop path-spelling differences so ./ and backslashes do not split a command."""
    tokens: list[str] = []
    for token in text.replace("\\", "/").split():
        while token.startswith("./"):
            token = token[2:]
        tokens.append(token)
    return " ".join(tokens)


def _paths_in(text: str) -> set[str]:
    return {_canonical_file(match) for match in _PATH_RE.findall(text)}


def _exception_names(text: str) -> set[str]:
    return {match for match in _EXCEPTION_RE.findall(text) if match not in {"Error", "Exception"}}


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def _near_output(left: str, right: str) -> bool:
    normalized_left = _normalize(left)
    normalized_right = _normalize(right)
    if normalized_left == normalized_right:
        return True
    if not normalized_left or not normalized_right:
        return False
    return SequenceMatcher(a=normalized_left, b=normalized_right).ratio() >= _OUTPUT_SIMILARITY


class _CommandLoop:
    def __init__(self, command: str, anchor_output: str, position: int, step: Step) -> None:
        self.command = command
        self.anchor_output = anchor_output
        self.positions = [position]
        self.steps = [step]


@rule
def command_loop(run: Run) -> list[Finding]:
    loops: list[_CommandLoop] = []
    for position, step in enumerate(_ordered(run)):
        if step.type != "command":
            continue
        command = _normalize_command(step.content)
        joined = False
        for loop in reversed(loops):
            if loop.command != command:
                continue
            # Older repeats of this command are farther away, so the window has closed.
            if position - loop.positions[-1] > _WINDOW_GAP:
                break
            if _near_output(step.output, loop.anchor_output):
                loop.positions.append(position)
                loop.steps.append(step)
                joined = True
                break
        if not joined:
            loops.append(_CommandLoop(command, step.output, position, step))

    findings: list[Finding] = []
    for loop in loops:
        if len(loop.steps) < 3:
            continue
        third = loop.steps[2]
        count = len(loop.steps)
        severity: Severity = "high" if count >= 5 else "medium"
        shown = loop.command if len(loop.command) <= 60 else f"{loop.command[:57]}..."
        findings.append(
            Finding(
                type="command_loop",
                step_index=third.index,
                severity=severity,
                explanation=(
                    f'Command "{shown}" repeated {count} times with near-identical output, '
                    f"and step {third.index} is the third repeat."
                ),
            ),
        )
    return findings


@rule
def edit_then_fail(run: Run) -> list[Finding]:
    steps = _ordered(run)
    test_runs = [step for step in steps if step.type == "test_run"]
    findings: list[Finding] = []
    for previous, current in zip(test_runs, test_runs[1:], strict=False):
        if previous.tests_failed is None or current.tests_failed is None:
            continue
        if current.tests_failed <= previous.tests_failed:
            continue
        edits = [
            step
            for step in steps
            if step.type == "edit" and previous.index < step.index < current.index
        ]
        if not edits:
            continue
        edited_file = edits[-1].file or "a file"
        findings.append(
            Finding(
                type="edit_then_fail",
                step_index=current.index,
                severity="medium",
                explanation=(
                    f"Edit of {edited_file} was followed by test_run step {current.index}, "
                    f"where tests_failed rose from {previous.tests_failed} "
                    f"to {current.tests_failed}."
                ),
            ),
        )
    return findings


@rule
def false_success_claim(run: Run) -> list[Finding]:
    steps = _ordered(run)
    if not steps or not run.agent_claimed_success or run.final_status != "fail":
        return []
    last = steps[-1]
    return [
        Finding(
            type="false_success_claim",
            step_index=last.index,
            severity="high",
            explanation="The agent claimed success, but final_status is fail.",
        ),
    ]


@rule
def gave_up_early(run: Run) -> list[Finding]:
    if run.final_status != "fail":
        return []
    steps = _ordered(run)
    if not steps:
        return []
    failing_at: int | None = None
    for position, step in enumerate(steps):
        if step.type == "test_run" and step.tests_failed is not None and step.tests_failed > 0:
            failing_at = position
            break
    if failing_at is None:
        return []
    steps_after = len(steps) - failing_at - 1
    if steps_after >= 5:
        return []
    if any(step.type == "edit" for step in steps[-3:]):
        return []
    failing = steps[failing_at]
    last = steps[-1]
    return [
        Finding(
            type="gave_up_early",
            step_index=last.index,
            severity="medium",
            explanation=(
                f"The first failing test_run is step {failing.index}, only {steps_after} "
                "steps follow it, and the last 3 steps contain no edits."
            ),
        ),
    ]


def _signatures_between(steps: list[Step], start_index: int, end_index: int) -> set[str]:
    signatures: set[str] = set()
    for step in steps:
        if step.type != "test_run" or not (start_index < step.index < end_index):
            continue
        if step.error_signature and step.error_signature.strip():
            signatures.add(step.error_signature.strip())
    return signatures


@rule
def symptom_fix(run: Run) -> list[Finding]:
    steps = _ordered(run)
    edit_steps = [
        step for step in steps if step.type == "edit" and step.file and step.file.strip()
    ]
    cohort = [step.file for step in edit_steps if step.file is not None]
    edits_by_file: dict[str, list[Step]] = {}
    for step in edit_steps:
        if step.file is None:
            continue
        edits_by_file.setdefault(_group_key(step.file, cohort), []).append(step)

    findings: list[Finding] = []
    for file_name, edits in edits_by_file.items():
        for offset in range(len(edits) - 2):
            first, second, third = edits[offset], edits[offset + 1], edits[offset + 2]
            common = sorted(
                _signatures_between(steps, first.index, second.index)
                & _signatures_between(steps, second.index, third.index),
            )
            if not common:
                continue
            findings.append(
                Finding(
                    type="symptom_fix",
                    step_index=third.index,
                    severity="high",
                    explanation=(
                        f"File {file_name} was edited 3 times while error_signature "
                        f"{common[0]!r} kept appearing in test runs between those edits."
                    ),
                ),
            )
            break
    return findings


def _error_needles(command: Step) -> list[str]:
    needles: list[str] = []
    if command.file and command.file.strip():
        needles.append(command.file.strip())
    if command.error_signature and len(command.error_signature.strip()) >= 4:
        needles.append(command.error_signature.strip())
    for line in command.output.splitlines():
        stripped = line.strip()
        if len(stripped) >= 8:
            needles.append(stripped)
    for match in _PATH_RE.findall(command.output):
        if len(match) >= 4:
            needles.append(match)
    return needles


def _failing_files(command: Step) -> set[str]:
    found: set[str] = set()
    if command.file and command.file.strip():
        found.add(_canonical_file(command.file))
    found.update(_paths_in(command.content))
    found.update(_paths_in(command.output))
    return {path for path in found if path}


def _addresses_error(command: Step, nxt: Step) -> bool:
    if nxt.type not in ("message", "edit"):
        return False
    haystack = "\n".join(part for part in (nxt.content, nxt.file or "") if part)
    failing = list(_failing_files(command))
    if nxt.file and failing:
        cohort = [*failing, nxt.file]
        edit_key = _group_key(nxt.file, cohort)
        if any(_group_key(path, cohort) == edit_key for path in failing):
            return True
    mentioned = _exception_names(command.output)
    if command.error_signature:
        mentioned.update(_exception_names(command.error_signature))
    if any(name in haystack for name in mentioned):
        return True
    return any(needle in haystack for needle in _error_needles(command))


@rule
def ignored_error(run: Run) -> list[Finding]:
    steps = _ordered(run)
    findings: list[Finding] = []
    for position, step in enumerate(steps[:-1]):
        if step.type != "command" or step.exit_code in (None, 0):
            continue
        nxt = steps[position + 1]
        if _addresses_error(step, nxt):
            continue
        findings.append(
            Finding(
                type="ignored_error",
                step_index=nxt.index,
                severity="low",
                explanation=(
                    f"Command step {step.index} exited {step.exit_code}, and step {nxt.index} "
                    "does not reference that error text or failing file."
                ),
            ),
        )
    return findings


@rule
def no_test_run(run: Run) -> list[Finding]:
    if run.final_status != "fail":
        return []
    steps = _ordered(run)
    if not steps or any(step.type == "test_run" for step in steps):
        return []
    last = steps[-1]
    return [
        Finding(
            type="no_test_run",
            step_index=last.index,
            severity="medium",
            explanation="The final_status is fail and the run contains no test_run step.",
        ),
    ]


__all__ = ["registered_rules"]
