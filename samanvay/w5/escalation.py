"""Escalation manager for Value trade-offs (W5, Spec §6.6).

Constructs Pareto option dialog payload, manages countdown deadlines,
and applies default conservative resolution on timeout.
"""

from typing import Any
from samanvay.core.models import (
    EscalationMessage,
    EscalationOption,
    EscalationPayload,
    Forecast,
)


class EscalationManager:
    """Manages active human escalations and timeouts."""

    def __init__(self, default_timeout_s: float = 30.0) -> None:
        self.default_timeout_s = default_timeout_s
        self.active_escalation: EscalationPayload | None = None
        self._counter: int = 0

    def create_escalation_from_forecast(
        self,
        forecast: Forecast,
        trigger_reason: str,
    ) -> EscalationMessage:
        """Build an EscalationMessage from a VALUE-classified Forecast."""
        self._counter += 1
        options: list[EscalationOption] = []

        for idx, cand in enumerate(forecast.candidates):
            is_default = (idx == 0)  # Plan A (current/conservative) is default
            tradeoff = (
                f"Expected aid {cand.esa_mean:.2f} (95% CI [{cand.esa_ci95[0]:.2f}, {cand.esa_ci95[1]:.2f}]), "
                f"agent loss risk {cand.p_agent_loss * 100:.1f}%, P1 failure risk {cand.p_p1_fail * 100:.1f}%."
            )
            options.append(
                EscalationOption(
                    id=cand.plan_id,
                    title=f"Plan {cand.plan_id}",
                    tradeoff_summary=tradeoff,
                    esa_ci95=cand.esa_ci95,
                    p_agent_loss=cand.p_agent_loss,
                    p_p1_fail=cand.p_p1_fail,
                    is_default=is_default,
                )
            )

        payload = EscalationPayload(
            escalation_id=self._counter,
            trigger_reason=trigger_reason,
            deadline_s=self.default_timeout_s,
            default_option_id=options[0].id if options else "P-current",
            options=options,
        )
        self.active_escalation = payload
        return EscalationMessage(payload=payload)

    def trigger_escalation(
        self,
        target_agent: str,
        reason: str,
        options: list[dict[str, Any]],
    ) -> EscalationPayload:
        """Trigger an escalation directly with custom Pareto options."""
        self._counter += 1
        esc_opts = [
            EscalationOption(
                id=opt["id"],
                title=opt.get("label", opt["id"]),
                tradeoff_summary=f"ESA {opt.get('esa', 2.0)}, loss risk {round(opt.get('loss_risk', 0.05)*100)}%",
                esa_ci95=(opt.get("esa", 2.0) - 0.2, opt.get("esa", 2.0) + 0.2),
                p_agent_loss=opt.get("loss_risk", 0.05),
                p_p1_fail=0.05,
                is_default=(idx == 0),
            )
            for idx, opt in enumerate(options)
        ]
        payload = EscalationPayload(
            escalation_id=self._counter,
            trigger_reason=f"[{target_agent}] {reason}",
            deadline_s=self.default_timeout_s,
            default_option_id=esc_opts[0].id if esc_opts else "P-current",
            options=esc_opts,
        )
        self.active_escalation = payload
        return payload

    def resolve_escalation(self, chosen_id: str) -> str:
        """Resolve active escalation with operator choice."""
        self.active_escalation = None
        return chosen_id

    def handle_timeout(self) -> str:
        """Default fallback on expiration."""
        if self.active_escalation:
            fallback = self.active_escalation.default_option_id
            self.active_escalation = None
            return fallback
        return "P-current"
