from app.analyzer import rules as rule_module
from app.analyzer.registry import Finding
from app.models import Run


def run_analysis(run: Run) -> list[Finding]:
    findings: list[Finding] = []
    for analyze in rule_module.registered_rules():
        findings.extend(analyze(run))
    findings.sort(key=lambda finding: (finding.step_index, finding.type))
    return findings


__all__ = ["Finding", "run_analysis"]
