"""Schema inference detector for chat endpoints."""

from __future__ import annotations

from typing import Any

from aiprobe.detectors.base import Detector, register
from aiprobe.detectors.context import ProbeContext
from aiprobe.detectors.schemas_known import REF_RESPONSE_SHAPE, classify_compat
from aiprobe.models.findings import DetectorCost, DetectorStatus, Finding
from aiprobe.utils.jsonshape import infer_shape, to_json_schema
from aiprobe.utils.log import get_logger

logger = get_logger(__name__)


@register
class SchemaDetector(Detector):
    name = "schema"
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

        if ctx.chat_payload:
            payload = dict(ctx.chat_payload)
            rounds_used = 0
        else:
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
            }
            rounds_used = 0

            for _ in range(3):
                try:
                    resp = await ctx.client.post(url, json=payload)
                    if resp.ok():
                        break

                    rounds_used += 1
                    if resp.status_code in (400, 422):
                        err_text = resp.text().lower()
                        # Auto-adjust payload based on common error patterns
                        if "model" in err_text and "model" not in payload:
                            payload["model"] = "gpt-3.5-turbo"
                        elif "messages" in err_text and "messages" not in payload:
                            payload["messages"] = [{"role": "user", "content": "ping"}]
                        elif "temperature" in err_text and "temperature" not in payload:
                            payload["temperature"] = 0.7
                        elif "unknown field" in err_text and "stream" in payload:
                            payload.pop("stream", None)
                        else:
                            # Generic fallback: add both if missing
                            payload.setdefault("model", "gpt-3.5-turbo")
                            payload.setdefault("messages", [{"role": "user", "content": "ping"}])
                    else:
                        break
                except Exception as exc:
                    logger.warning(f"Schema probe failed: {exc}")
                    break

        try:
            resp = await ctx.client.post(url, json=payload)
            if not resp.ok():
                return self._finding(DetectorStatus.FAILED, 0.0, error=f"Status {resp.status_code}")

            resp_json = resp.json()
            resp_shape = infer_shape(resp_json)
            req_shape = infer_shape(payload)
            compat = classify_compat(resp_shape, REF_RESPONSE_SHAPE)

            return self._finding(
                DetectorStatus.DETECTED,
                confidence=0.9,
                data={
                    "request_shape": to_json_schema(req_shape),
                    "response_shape": to_json_schema(resp_shape),
                    "schema_compat": compat.value,
                    "rounds_used": rounds_used,
                    "working_payload": payload,
                },
            )
        except Exception as exc:
            return self._finding(DetectorStatus.FAILED, 0.0, error=str(exc))
