"""Deterministic mission grammar parser (W1 Mission Understanding, Spec §6.2).

Aligns with INSARAG Guidelines Vol. III Annex B20 (ASR 1-3).
Translates plain text objectives into schema-validated MissionSpec without external LLMs.
"""

import re
from typing import NamedTuple
from samanvay.core.models import Constraint, MissionPhase, MissionSpec, PolicyConfig


class ParseResult(NamedTuple):
    spec: MissionSpec
    unparsed_spans: list[str]


def parse_mission_objective(text: str) -> ParseResult:
    """Parse a typed mission objective into a validated MissionSpec.

    Examples:
    - "Sweep all sectors for assessment, then focus on sectors B and C, deliver medkits on survivor confirmation, maintain comms, avoid plume"
    - "Search sector A, maintain link, avoid plume"
    """
    clean_text = text.strip()
    unparsed_spans: list[str] = []

    phases: list[MissionPhase] = []
    constraints: list[Constraint] = []
    policy = PolicyConfig()

    lowered = clean_text.lower()

    # 1. Check constraints
    if "comms" in lowered or "contact" in lowered or "link" in lowered:
        constraints.append(Constraint(type="comms", rule="maintain_link_all"))

    if "plume" in lowered or "smoke" in lowered or "hazard" in lowered or "gas" in lowered or "fire" in lowered:
        constraints.append(Constraint(type="avoid", hazard="plume"))

    # 2. Check ASR Phase 1 (Wide area assessment / all sectors)
    if "all" in lowered or "wide" in lowered or "assessment" in lowered or "assess" in lowered or "whole area" in lowered or "asr 1" in lowered or "sweep all" in lowered:
        phases.append(
            MissionPhase(
                asr=1,
                area="all",
                goal="wide_area_assessment",
                priority=1,
            )
        )

    # 3. Check ASR Phase 2 (Sector specific sweep / prioritization)
    sector_match = re.findall(r"\bsector[s]?\s+([a-d](?:\s*,\s*[a-d])*(?:\s+and\s+[a-d])?)", lowered)
    target_sectors: list[str] = []
    if sector_match:
        for match in sector_match:
            letters = re.findall(r"\b[a-d]\b", match)
            target_sectors.extend([l.upper() for l in letters])

    # Direct letters like "sector B and C"
    if not target_sectors:
        for s in ["A", "B", "C", "D"]:
            if f"sector {s.lower()}" in lowered or f"sectors {s.lower()}" in lowered:
                target_sectors.append(s)

    target_sectors = sorted(list(set(target_sectors)))
    if target_sectors:
        phases.append(
            MissionPhase(
                asr=2,
                sectors=target_sectors,
                goal="sector_assessment",
                priority=2,
            )
        )
    elif not phases:
        # Default to all sectors if none specified
        phases.append(
            MissionPhase(
                asr=1,
                area="all",
                goal="wide_area_assessment",
                priority=1,
            )
        )

    # 4. Check ASR Phase 3 (Rescue / Deliver on survivor confirmation)
    if "deliver" in lowered or "drop" in lowered or "medkit" in lowered or "kit" in lowered or "rescue" in lowered or "survivor" in lowered:
        spawn_items = ["DELIVER:medkit"]
        phases.append(
            MissionPhase(
                asr=3,
                trigger="survivor_confirmed",
                spawn=spawn_items,
                priority=3,
            )
        )

    # 5. Extract unparsed tokens for operator feedback
    known_keywords = {
        "sweep", "all", "sectors", "sector", "for", "assessment", "assess", "whole", "area", "then", "focus", "on", "and",
        "deliver", "medkits", "medkit", "kits", "kit", "survivor", "survivors", "confirmation", "anyone", "found",
        "maintain", "keep", "everyone", "comms", "link", "contact", "avoid", "plume", "smoke", "fire", "hazard",
        "search", "scan", "a", "b", "c", "d", "to", "in", "with", "the"
    }
    words = re.findall(r"\b\w+\b", lowered)
    for w in words:
        if w not in known_keywords:
            unparsed_spans.append(w)

    spec = MissionSpec(
        phases=phases,
        constraints=constraints,
        policy=policy,
    )

    return ParseResult(spec=spec, unparsed_spans=unparsed_spans)
