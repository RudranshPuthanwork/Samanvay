"""Fidelity test for 1,000 generated contrastive explanations (Spec §6.7.2).

Extracts and mechanically validates all numbers, candidate choices, and
classification tones over 1,000 generated decision records.
"""

import random
from samanvay.core.models import DecisionClassification, DecisionKind, DecisionRecord
from samanvay.w6.fidelity import check_explanation_fidelity
from samanvay.w6.templates import generate_contrastive_explanation


def test_1000_explanation_fidelity():
    """Verify explanation fidelity over 1,000 generated records with randomized metrics."""
    rng = random.Random(42)

    for i in range(1000):
        classification = rng.choice([
            DecisionClassification.FACT,
            DecisionClassification.VALUE,
            DecisionClassification.SAFETY,
            DecisionClassification.POLICY,
        ])
        delta_esa = round(rng.uniform(0.1, 1.5), 2)
        delta_risk = round(rng.uniform(0.02, 0.35), 2)
        hazard = round(rng.uniform(0.5, 0.95), 2)
        lead_s = float(rng.randint(20, 60))

        if classification == DecisionClassification.FACT:
            kind_str = rng.choice(["SWITCH_PLAN", "REROUTE", "ASSIGN"])
            chosen = "plan B" if kind_str != "ASSIGN" else "cargo-1"
            runner_up = "plan A" if kind_str != "ASSIGN" else "rover-1"
            ci_min = round(delta_esa * 0.6, 2)
            ci_max = round(delta_esa * 1.3, 2)
            exp = generate_contrastive_explanation(
                kind=kind_str,
                classification=classification,
                chosen=chosen,
                runner_up=runner_up,
                delta_esa=delta_esa,
                ci95_esa=(ci_min, ci_max),
                risk_before_after=(3.0, 2.0),
                p1_fail_before_after=(22.0, 8.0),
            )
            expected_numbers = [delta_esa]

        elif classification == DecisionClassification.VALUE:
            kind_str = "ESCALATE"
            chosen = "P-repair"
            runner_up = "P-current"
            exp = generate_contrastive_explanation(
                kind=kind_str,
                classification=classification,
                chosen=chosen,
                runner_up=runner_up,
                delta_esa=delta_esa,
                delta_risk=delta_risk,
            )
            expected_numbers = [round(delta_risk * 100, 0)]

        elif classification == DecisionClassification.SAFETY:
            kind_str = "SHIELD_OVERRIDE"
            chosen = "COMMAND_REJECTED"
            runner_up = "COMMAND_APPROVED"
            exp = generate_contrastive_explanation(
                kind=kind_str,
                classification=classification,
                chosen=chosen,
                runner_up=runner_up,
                hazard=hazard,
                hazard_lead_s=lead_s,
            )
            expected_numbers = [hazard, lead_s]

        else:
            kind_str = "POLICY_CHOICE"
            chosen = "plan B"
            runner_up = "plan A"
            exp = generate_contrastive_explanation(
                kind=kind_str,
                classification=classification,
                chosen=chosen,
                runner_up=runner_up,
                policy_reference="triage_exchange",
            )
            expected_numbers = []

        record = DecisionRecord(
            id=i + 1,
            t=float(i * 5),
            kind=DecisionKind(kind_str),
            classification=classification,
            explanation=exp,
            chosen=chosen,
            options=[chosen, runner_up],
            prev_hash=f"prev_hash_{i}",
            hash=f"hash_{i}",
        )

        valid, msg = check_explanation_fidelity(record, expected_numbers=expected_numbers)
        assert valid, f"Fidelity failure on record #{i+1}: {msg}"
