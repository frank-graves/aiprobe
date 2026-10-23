"""Endpoint discovery detector with controlled concurrency."""

from __future__ import annotations

import asyncio
from enum import StrEnum
from typing import Any

from aiprobe.detectors.base import Detector, register
from aiprobe.detectors.candidates import (
    EndpointCandidate,
    extract_paths_from_html,
    generate_candidates,
)
from aiprobe.detectors.context import ProbeContext
from aiprobe.models.findings import DetectorCost, DetectorStatus, Finding
from aiprobe.utils.log import get_logger

logger = get_logger(__name__)


class EndpointStatus(StrEnum):
    EXISTS_PUBLIC = "exists_public"
    EXISTS_PROTECTED = "exists_protected"
    EXISTS_BAD_PAYLOAD = "exists_bad_payload"
    EXISTS_METHOD_MISMATCH = "exists_method_mismatch"
    EXISTS_RATE_LIMITED = "exists_rate_limited"
    EXISTS_SERVER_ERROR = "exists_server_error"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"
    ERROR = "error"


def _classify_status(
    code: int, content_type: str = "", body: bytes = b""
) -> tuple[EndpointStatus, float]:
    """Classify HTTP status codes into EndpointStatus and confidence."""
    if 200 <= code < 300:
        # 1. Falso positivo clásico: Devuelve HTML en lugar de JSON (SPA)
        if "text/html" in content_type:
            return EndpointStatus.NOT_FOUND, 0.9

        # 2. Falso positivo moderno: Devuelve 200 OK con un JSON de error
        if "application/json" in content_type and body:
            try:
                text = body.decode("utf-8", errors="replace").lower()
                if "not found" in text or '"error"' in text or '"detail"' in text:
                    return EndpointStatus.NOT_FOUND, 0.9
            except Exception:
                pass

        return EndpointStatus.EXISTS_PUBLIC, 0.9

    if code in (400, 422):
        return EndpointStatus.EXISTS_BAD_PAYLOAD, 0.75
    if code in (401, 403):
        return EndpointStatus.EXISTS_PROTECTED, 0.9
    if code in (404, 410):
        return EndpointStatus.NOT_FOUND, 0.9
    if code == 405:
        return EndpointStatus.EXISTS_METHOD_MISMATCH, 0.9
    if code == 429:
        return EndpointStatus.EXISTS_RATE_LIMITED, 0.75
    if 500 <= code < 600:
        return EndpointStatus.EXISTS_SERVER_ERROR, 0.4
    return EndpointStatus.UNKNOWN, 0.4


@register
class EndpointsDetector(Detector):
    name = "endpoints"
    category = "api"
    cost = DetectorCost.CHEAP

    async def run(self, target: str, context: dict[str, Any]) -> Finding:
        try:
            ctx = ProbeContext.model_validate(context)
        except Exception as exc:
            return self._finding(DetectorStatus.FAILED, 0.0, error=f"Invalid context: {exc}")

        base_url = target.rstrip("/")
        candidates = generate_candidates(ctx.provider_spec)

        bundle_discovered: list[str] = []
        if ctx.parse_bundles:
            try:
                resp = await ctx.client.get(base_url + "/")
                if resp.ok():
                    discovered = extract_paths_from_html(resp.text())
                    for p in list(discovered)[: ctx.max_bundle_paths]:
                        bundle_discovered.append(p)
                        if not any(c.path == p for c in candidates):
                            candidates.append(
                                EndpointCandidate(
                                    name=p.strip("/").split("/")[-1],
                                    path=p,
                                    method="GET",
                                    source="bundle",
                                )
                            )
            except Exception as exc:
                logger.warning(f"Failed to parse bundles: {exc}")

        sem = asyncio.Semaphore(5)
        results: dict[tuple[str, str], dict[str, Any]] = {}

        async def probe_candidate(cand: EndpointCandidate) -> None:
            async with sem:
                url = base_url + cand.path
                kwargs: dict[str, Any] = {}
                if cand.method == "POST":
                    kwargs["json"] = {}

                try:
                    resp = await ctx.client.request(cand.method, url, **kwargs)
                    content_type = resp.headers.get("content-type", "").lower()

                    # Pasamos el cuerpo de la respuesta a la clasificación
                    status, conf = _classify_status(resp.status_code, content_type, resp.content)
                    current_method = cand.method

                    if status == EndpointStatus.EXISTS_METHOD_MISMATCH:
                        allow = resp.headers.get("allow", "")
                        if allow:
                            allowed_method = allow.split(",")[0].strip().upper()
                            if allowed_method and allowed_method != current_method:
                                retry_resp = await ctx.client.request(allowed_method, url, **kwargs)
                                retry_ct = retry_resp.headers.get("content-type", "").lower()
                                retry_status, retry_conf = _classify_status(
                                    retry_resp.status_code, retry_ct, retry_resp.content
                                )
                                if retry_status not in (
                                    EndpointStatus.ERROR,
                                    EndpointStatus.UNKNOWN,
                                ):
                                    status = retry_status
                                    conf = retry_conf
                                    current_method = allowed_method

                    key = (current_method, cand.path)
                    if key not in results or conf > results[key]["confidence"]:
                        results[key] = {
                            "name": cand.name,
                            "path": cand.path,
                            "method": current_method,
                            "status": status.value,
                            "requires_auth": status == EndpointStatus.EXISTS_PROTECTED,
                            "confidence": conf,
                            "evidence": {
                                "status_code": resp.status_code,
                                "content_type": content_type or "missing",
                                "body_snippet": resp.text()[:50] if resp.content else "",
                            },
                            "source": cand.source,
                        }
                except Exception as exc:
                    logger.debug(f"Probe failed for {cand.path}: {exc}")
                    key = (cand.method, cand.path)
                    if key not in results:
                        results[key] = {
                            "name": cand.name,
                            "path": cand.path,
                            "method": cand.method,
                            "status": EndpointStatus.ERROR.value,
                            "requires_auth": False,
                            "confidence": 0.4,
                            "evidence": {"error": str(exc)},
                            "source": cand.source,
                        }

        await asyncio.gather(*(probe_candidate(c) for c in candidates))

        endpoints_data: dict[str, Any] = {}
        not_found_data: dict[str, Any] = {}

        sorted_results = sorted(
            results.values(), key=lambda x: (-x["confidence"], x["source"] != "provider")
        )

        for res in sorted_results:
            name = res["name"]
            if res["status"] == EndpointStatus.NOT_FOUND.value:
                if name not in not_found_data:
                    not_found_data[name] = res
                continue

            if name not in endpoints_data:
                endpoints_data[name] = {
                    "path": res["path"],
                    "method": res["method"],
                    "status": res["status"],
                    "requires_auth": res["requires_auth"],
                    "confidence": res["confidence"],
                    "evidence": res["evidence"],
                }

        return self._finding(
            DetectorStatus.DETECTED,
            confidence=0.8,
            data={
                "endpoints": endpoints_data,
                "bundle_discovered": bundle_discovered,
                "probed_count": len(candidates),
                "found_count": len(endpoints_data),
                "not_found": not_found_data,
            },
        )
