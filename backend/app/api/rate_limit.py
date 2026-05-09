from __future__ import annotations

import time
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status


@dataclass
class FixedWindowRateLimiter:
    max_requests: int
    window_seconds: float
    _hits: dict[str, list[float]] = field(default_factory=dict)

    def check(self, key: str, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        hits = [hit for hit in self._hits.get(key, []) if hit > cutoff]
        if len(hits) >= self.max_requests:
            retry_after = max(1, int(self.window_seconds - (current - hits[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(current)
        self._hits[key] = hits

    def reset(self) -> None:
        self._hits.clear()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or "unknown"
    if request.client is None:
        return "unknown"
    return request.client.host or "unknown"
