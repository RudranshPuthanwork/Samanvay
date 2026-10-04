"""Comms message queue with Value of Information (VoI) ranking (Spec §6.4.5)."""

from samanvay.core.models import CommsQueueItem


class CommsQueue:
    """Rate-limited comms queue prioritized by Value of Information (VoI)."""

    def __init__(self, max_packets_per_tick: int = 4) -> None:
        self.max_packets_per_tick = max_packets_per_tick
        self._items: list[CommsQueueItem] = []

    def enqueue(self, item_id: str, recipient: str, msg_type: str, voi_score: float) -> None:
        """Enqueue message with a VoI score."""
        self._items.append(
            CommsQueueItem(
                id=item_id,
                recipient=recipient,
                type=msg_type,
                voi_score=voi_score,
                sent=False,
            )
        )

    def process_tick(self) -> tuple[list[CommsQueueItem], list[str]]:
        """Dispatch up to budget packets prioritized by highest VoI score."""
        # Sort descending by VoI
        self._items.sort(key=lambda x: x.voi_score, reverse=True)

        sent_ids: list[str] = []
        budget = self.max_packets_per_tick

        new_items: list[CommsQueueItem] = []
        for it in self._items:
            if budget > 0 and not it.sent:
                sent_ids.append(it.id)
                new_items.append(it.model_copy(update={"sent": True}))
                budget -= 1
            else:
                new_items.append(it)

        self._items = [i for i in new_items if not i.sent]
        return new_items, sent_ids

    def get_items(self) -> list[CommsQueueItem]:
        return list(self._items)
