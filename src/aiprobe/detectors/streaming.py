"""Streaming format detection (SSE, JSONL, chunked)."""

from __future__ import annotations

import json
from typing import Any

from aiprobe.detectors.base import Detector, register
from aiprobe.detectors.context import ProbeContext
from aiprobe.models.findings import DetectorCost, DetectorStatus, Finding
from aiprobe.models.profile import StreamFormat
from aiprobe.utils.log import get_logger

logger = get_logger(__name__)


@register
class StreamingDetector(Detector):
    name = "streaming"
    category = "api"
    cost = DetectorCost.CHEAP

    async def run(self, target: str, context: dict[str, Any]) -> Finding:
        try:
            ctx = ProbeContext.model_validate(context)
        except Exception as exc:
            return self._finding(DetectorStatus.FAILED, 0.0, error=f"Invalid context: {exc}")

        chat_ep = ctx.endpoints.get("chat")
        if not chat_ep:
            return self._finding(DetectorStatus.SKIPPED, 0.0, data={"reason": "no chat endpoint"})

        url = target.rstrip("/") + chat_ep.path
        payload = ctx.chat_payload or {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "ping"}],
        }
        payload = dict(payload)
        payload["stream"] = True

        try:
            resp = await ctx.client.post(url, json=payload, stream=True)
            content_type = resp.headers.get("content-type", "").lower()

            chunks = []
            async for chunk in ctx.client.stream("POST", url, json=payload):
                chunks.append(chunk)
            body = b"".join(chunks)

            evidence_head = repr(body[:200])
            has_done = b"data: [DONE]" in body

            fmt = StreamFormat.UNKNOWN

            # 1. Header check
            if "text/event-stream" in content_type:
                fmt = StreamFormat.SSE
            elif "application/x-ndjson" in content_type or "application/jsonl" in content_type:
                fmt = StreamFormat.JSONL
            else:
                # 2. Body heuristics
                text = body.decode("utf-8", errors="replace")
                lines = [line.strip() for line in text.splitlines() if line.strip()]

                if any(line.startswith("data: ") for line in lines) or has_done:
                    fmt = StreamFormat.SSE
                else:
                    try:
                        json.loads(text)
                        fmt = StreamFormat.NONE
                    except json.JSONDecodeError:
                        if lines:
                            all_json = True
                            for line in lines:
                                try:
                                    json.loads(line)
                                except json.JSONDecodeError:
                                    all_json = False
                                    break
                            fmt = StreamFormat.JSONL if all_json else StreamFormat.CHUNKED
                        elif body.strip():
                            fmt = StreamFormat.CHUNKED

            return self._finding(
                DetectorStatus.DETECTED,
                confidence=0.95 if fmt != StreamFormat.UNKNOWN else 0.4,
                data={
                    "format": fmt.value,
                    "content_type": content_type,
                    "evidence_head": evidence_head,
                    "has_done_marker": has_done,
                },
            )
        except Exception as exc:
            logger.error("Streaming detection failed: %s", exc)
            return self._finding(DetectorStatus.FAILED, 0.0, error=str(exc))
