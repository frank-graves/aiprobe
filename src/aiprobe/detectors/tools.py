"""Tool calling capability detector."""

from __future__ import annotations

from typing import Any

from aiprobe.detectors.base import Detector, register
from aiprobe.detectors.context import ProbeContext
from aiprobe.models.findings import DetectorCost, DetectorStatus, Finding
from aiprobe.utils.log import get_logger

logger = get_logger(__name__)


@register
class ToolsDetector(Detector):
    name = "tools"
    category = "api"
    cost = DetectorCost.EXPENSIVE

    async def run(self, target: str, context: dict[str, Any]) -> Finding:
        try:
            ctx = ProbeContext.model_validate(context)
        except Exception as exc:
            return self._finding(DetectorStatus.FAILED, 0.0, error=f"Invalid context: {exc}")

        chat_ep = ctx.endpoints.get("chat")
        if not chat_ep:
            return self._finding(DetectorStatus.SKIPPED, 0.0, data={"reason": "no chat endpoint"})

        url = target.rstrip("/") + chat_ep.path

        base_payload: dict[str, Any] = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Call the ping function"}],
        }

        ping_tool = {
            "type": "function",
            "function": {
                "name": "ping",
                "description": "A simple ping function",
                "parameters": {"type": "object", "properties": {}},
            },
        }

        variants: list[dict[str, Any]] = [
            {"tools": [ping_tool], "tool_choice": "auto"},
            {"functions": [ping_tool], "function_call": "auto"},
            {"tools": [ping_tool]},
        ]

        variants_tried = []
        supported = False
        fmt = None
        evidence = {}

        for v in variants:
            variants_tried.append(list(v.keys()))
            payload = {**base_payload, **v}

            try:
                resp = await ctx.client.post(url, json=payload)
                if resp.ok():
                    text = resp.text().lower()
                    if "tool_calls" in text or '"finish_reason": "tool_calls"' in text:
                        supported = True
                        fmt = "openai"
                        evidence = {"status": 200, "matched": "tool_calls"}
                        break
                    else:
                        evidence = {"status": 200, "matched": "accepted_ignored"}
                elif resp.status_code in (400, 422):
                    err_text = resp.text().lower()
                    if "tool" in err_text or "function" in err_text:
                        evidence = {"status": resp.status_code, "matched": "rejected"}
                    else:
                        evidence = {"status": resp.status_code, "matched": "unknown"}
            except Exception as exc:
                logger.debug(f"Tool variant failed: {exc}")
                evidence = {"error": str(exc)}

        return self._finding(
            DetectorStatus.DETECTED,
            confidence=0.9 if supported else 0.5,
            data={
                "supported": supported,
                "format": fmt,
                "variants_tried": variants_tried,
                "evidence": evidence,
            },
        )
