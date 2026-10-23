"""Transport requirements detector (HTTP/2, TLS fingerprint, headers)."""

from __future__ import annotations

from typing import Any

from aiprobe.detectors.base import Detector, register
from aiprobe.detectors.context import ProbeContext
from aiprobe.models.findings import DetectorCost, DetectorStatus, Finding
from aiprobe.utils.log import get_logger

logger = get_logger(__name__)


@register
class TransportDetector(Detector):
    name = "transport"
    category = "network"
    cost = DetectorCost.CHEAP

    async def run(self, target: str, context: dict[str, Any]) -> Finding:
        try:
            ctx = ProbeContext.model_validate(context)
        except Exception as exc:
            return self._finding(
                DetectorStatus.FAILED, 0.0, error=f"Invalid context: {exc}"
            )

        url = target if target.startswith("http") else f"https://{target}"
        if not url.endswith(ctx.probe_paths[0]):
            url = url.rstrip("/") + ctx.probe_paths[0]

        signals: list[str] = []
        http2 = False
        tls_fingerprint: str | None = None
        required_headers: list[str] = []

        try:
            # 1. HTTP/2 test
            resp_http1 = await ctx.client.get(url, http_version=1)
            resp_default = await ctx.client.get(url)
            if not resp_http1.ok() and resp_default.ok():
                http2 = True
                signals.append("http2_required")

            # 2. TLS fingerprint test
            resp_chrome = await ctx.client.get(url, impersonate="chrome")
            resp_plain = await ctx.client.get(url, impersonate=None)
            if resp_chrome.ok() and not resp_plain.ok():
                tls_fingerprint = "chrome"
                signals.append("tls_fingerprint_required")

            # 3. Required headers test
            empty_headers: dict[str, str] = {}
            full_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Fetch-Site": "none",
            }
            resp_empty = await ctx.client.get(url, headers=empty_headers)
            resp_full = await ctx.client.get(url, headers=full_headers)
            if resp_full.ok() and not resp_empty.ok():
                required_headers = list(full_headers.keys())
                signals.append("headers_required")

            return self._finding(
                DetectorStatus.DETECTED if signals else DetectorStatus.OK,
                confidence=0.8 if signals else 0.9,
                data={
                    "http2": http2,
                    "tls_fingerprint": tls_fingerprint,
                    "required_headers": required_headers,
                    "signals": signals,
                },
            )

        except Exception as exc:
            logger.error("Transport detection failed: %s", exc)
            return self._finding(DetectorStatus.FAILED, 0.0, error=str(exc))
