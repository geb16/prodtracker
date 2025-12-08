"""Lightweight user alert shim.

Provides a best-effort local notification mechanism. If desktop notification
libraries are unavailable, falls back to logging/print to avoid breaking flows.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    # Optional desktop notifier; not required.
    from plyer import notification  # type: ignore
except Exception:  # pragma: no cover
    notification = None  # type: ignore


def alert_user_now(title: str, message: str) -> None:
    """Show a local alert to the user (best-effort, non-fatal).

    Args:
        title: Short title for the notification.
        message: Descriptive message for the user.
    """
    if notification:
        try:
            notification.notify(title=title, message=message, timeout=5)
            return
        except Exception as exc:  # pragma: no cover
            logger.debug("Desktop notification failed: %s", exc)

    # Fallbacks
    try:
        # Minimal stdout fallback to ensure visibility
        print(f"[ALERT] {title}: {message}")
    except Exception:
        # Last resort: only log
        logger.info("ALERT - %s: %s", title, message)
