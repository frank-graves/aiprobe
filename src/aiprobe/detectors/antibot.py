"""Anti-bot classification detector."""

from __future__ import annotations

import re
from typing import Any

from aiprobe.core.http import HttpResponse
from aiprobe.detectors.base import Detector, register
from aiprobe.detectors.context import ProbeContext
from aiprobe.detectors.signatures import ANTIBOT_SIGNATURES, AntibotSignature
from aiprobe.models.findings import DetectorCost, DetectorStatus, Finding
from aiprobe.models.profile import AntibotType, BypassStrategy
from aiprobe.utils.log import get_logger

logger = get_logger(__name__)


@register
class AntibotDetector(Detector):
    name = "antibot"
    category = "security"
    cost = DetectorCost.CHEAP

    async def run(self, target: str, context: dict[str, Any]) -> Finding:
        try:
            ctx = ProbeContext.model_validate(context)
        except Exception as exc:
            return self._finding(DetectorStatus.FAILED, 0.0, error=f"Invalid context: {exc}")

        url = target if target.startswith("http") else f"https://{target}"
        if not url.endswith(ctx.probe_paths[0]):
            url = url.rstrip("/") + ctx.probe_paths[0]

        try:
            # Differential TLS fingerprint test
            resp_a = await ctx.client.get(url, impersonate="chrome")
            resp_b = await ctx.client.get(url, impersonate=None)

            if resp_a.ok() and not resp_b.ok() and resp_b.status_code in (403, 503):
                return self._finding(
                    DetectorStatus.DETECTED,
                    confidence=1.0,
                    data={
                        "type": AntibotType.CF_TLS.value,
                        "bypass": BypassStrategy.CURL_CFFI.value,
                        "impersonate": "chrome",
                        "signals": ["differential_tls"],
                        "evidence": {
                            "chrome_status": resp_a.status_code,
                            "plain_status": resp_b.status_code,
                        },
                    },
                )

            best_sig: AntibotSignature | None = None
            best_score = 0.0
            best_signals: list[str] = []

            for sig in ANTIBOT_SIGNATURES:
                score, signals = self._evaluate_signature(sig, resp_a)
                if score > best_score:
                    best_score = score
                    best_sig = sig
                    best_signals = signals

            if best_sig and best_score >= 0.5:
                bypass = self._derive_bypass(best_sig)
                return self._finding(
                    DetectorStatus.DETECTED,
                    confidence=min(1.0, best_score),
                    data={
                        "type": best_sig.name.value,
                        "bypass": bypass.value,
                        "impersonate": None if bypass != BypassStrategy.CURL_CFFI else "chrome",
                        "signals": best_signals,
                        "evidence": {"status_code": resp_a.status_code},
                    },
                )

            # Blocked but no signature matched
            if not resp_a.ok() or not resp_b.ok():
                return self._finding(
                    DetectorStatus.DETECTED,
                    confidence=0.5,
                    data={
                        "type": AntibotType.UNKNOWN.value,
                        "bypass": BypassStrategy.BROWSER.value,
                        "impersonate": None,
                        "signals": ["unidentified_block"],
                        "evidence": {"status_code": resp_a.status_code},
                    },
                )

            # Clean
            return self._finding(
                DetectorStatus.OK,
                confidence=0.9,
                data={
                    "type": AntibotType.NONE.value,
                    "bypass": BypassStrategy.NONE.value,
                    "impersonate": None,
                    "signals": [],
                    "evidence": {"status_code": resp_a.status_code},
                },
            )

        except Exception as exc:
            logger.error("Antibot detection failed: %s", exc)
            return self._finding(DetectorStatus.FAILED, 0.0, error=str(exc))

    def _evaluate_signature(
        self, sig: AntibotSignature, resp: HttpResponse
    ) -> tuple[float, list[str]]:
        score = 0.0
        signals: list[str] = []

        for h in sig.header_keys:
            if h.lower() in resp.headers:
                score += sig.weight
                signals.append(f"header:{h}")

        for p in sig.header_patterns:
            for k, v in resp.headers.items():
                if re.search(p, k, re.I) or re.search(p, v, re.I):
                    score += sig.weight
                    signals.append(f"header_pattern:{p}")
                    break

        body_lower = resp.text().lower()
        for sub in sig.body_substrings:
            if sub.lower() in body_lower:
                score += sig.weight
                signals.append(f"body:{sub}")

        set_cookie = resp.headers.get("set-cookie", "").lower()
        for c in sig.cookie_names:
            if f"{c.lower()}=" in set_cookie:
                score += sig.weight
                signals.append(f"cookie:{c}")

        # A status code alone is not evidence of any particular vendor; it only
        # reinforces a match that already has a header/body/cookie signal.
        if signals and resp.status_code in sig.status_codes:
            score += sig.weight
            signals.append(f"status:{resp.status_code}")

        return score, signals

    def _derive_bypass(self, sig: AntibotSignature) -> BypassStrategy:
        if sig.name == AntibotType.NONE:
            return BypassStrategy.NONE
        if sig.name == AntibotType.CF_TLS:
            return BypassStrategy.CURL_CFFI
        if sig.is_js_challenge or sig.requires_browser:
            return BypassStrategy.BROWSER
        return BypassStrategy.BROWSER
