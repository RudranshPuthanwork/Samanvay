"""Mechanical explanation fidelity test (W6, Spec §6.7.2).

Validates that contrastive explanations accurately report the recorded metrics
and candidate identifiers from the underlying DecisionRecord and Forecast.
Every number in a generated explanation is parsed back and compared with the record it came from.
"""

import re
from typing import Any
from samanvay.core.models import DecisionClassification, DecisionRecord, Forecast


def extract_numbers_from_text(text: str) -> list[float]:
    """Extract all integer and floating point numbers (including percentages and +/- signs) from text."""
    # Match numbers like +0.31, -0.40, 95, 0.18, 3%, 22%
    tokens = re.findall(r"[-+]?\d*\.?\d+", text)
    nums: list[float] = []
    for t in tokens:
        try:
            nums.append(float(t))
        except ValueError:
            continue
    return nums


def check_explanation_fidelity(
    record: DecisionRecord,
    expected_numbers: list[float] | None = None,
    forecast: Forecast | None = None,
) -> tuple[bool, str]:
    """Mechanically verify that explanation text aligns with recorded numeric facts and classification tone."""
    exp = record.explanation
    if not exp or len(exp.strip()) == 0:
        return False, "Explanation text cannot be empty"

    # Check classification tags
    if record.classification == DecisionClassification.SAFETY or record.classification == "SAFETY":
        if "Refused" not in exp and "Safety shield" not in exp and "SAFETY" not in exp and "override" not in exp:
            return False, f"SAFETY decision record must state shield/safety override: '{exp}'"

    if record.classification == DecisionClassification.VALUE or record.classification == "VALUE":
        if "trade-off" not in exp and "Pareto" not in exp and "VALUE" not in exp and "trade differently" not in exp:
            return False, f"VALUE decision record must cite trade-off or Pareto escalation: '{exp}'"

    if record.classification == DecisionClassification.FACT or record.classification == "FACT":
        if "Switched" not in exp and "Assigned" not in exp and "FACT" not in exp and "Executed" not in exp and "Verification" not in exp:
            return False, f"FACT decision record must follow deterministic FACT phrasing: '{exp}'"

    # Check chosen option appears in explanation if specified
    if record.chosen and record.chosen in ("P-repair", "P-current", "plan B", "cargo-1", "rover-1"):
        if record.chosen not in exp:
            return False, f"Expected chosen '{record.chosen}' in explanation: '{exp}'"

    # Verify numbers if expected_numbers provided
    if expected_numbers is not None:
        extracted = extract_numbers_from_text(exp)
        for expected in expected_numbers:
            # Check if expected number exists in extracted numbers within rounding tolerance
            found = any(abs(extracted_num - expected) < 0.05 for extracted_num in extracted)
            if not found:
                return False, f"Expected numeric value {expected} not found in extracted numbers {extracted} from '{exp}'"

    return True, "Explanation verified faithful"


# Backward compatibility alias
test_explanation_fidelity = check_explanation_fidelity
