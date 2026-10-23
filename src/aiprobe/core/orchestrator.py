"""Orchestrates the execution of the probe pipeline."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from aiprobe.core.browser import BrowserDriver
from aiprobe.core.pipeline import PipelineStep
from aiprobe.core.session import SessionManager
from aiprobe.core.telemetry import StepEvent, StepObserver
from aiprobe.detectors.base import DETECTORS
from aiprobe.detectors.context import ProbeContext
from aiprobe.models.findings import DetectorCost, DetectorStatus, Finding
from aiprobe.models.profile import (
    CURRENT_SCHEMA_VERSION,
    AntibotInfo,
    AntibotType,
    AuthInfo,
    AuthScheme,
    BypassStrategy,
    EndpointInfo,
    Profile,
    SchemaCompat,
    StreamFormat,
    TransportInfo,
)
from aiprobe.providers.base import ProviderSpec
from aiprobe.utils.log import get_logger

logger = get_logger(__name__)


class OrchestratorConfig:
    """Runtime configuration for the orchestrator."""

    def __init__(
        self,
        skip_expensive: bool = False,
        skip_browser: bool = False,
        browser_driver: BrowserDriver | None = None,
    ) -> None:
        self.skip_expensive = skip_expensive
        self.skip_browser = skip_browser
        self.browser_driver = browser_driver


class Orchestrator:
    """Runs a sequence of detectors, passing context between them."""

    def __init__(
        self,
        steps: tuple[PipelineStep, ...],
        session_manager: SessionManager,
        config: OrchestratorConfig,
        observer: StepObserver | None = None,
    ) -> None:
        self.steps = steps
        self.session_manager = session_manager
        self.config = config
        self.observer = observer

    async def run(
        self, target: str, provider_spec: ProviderSpec | None = None
    ) -> dict[str, Finding]:
        """Execute the pipeline and return all findings."""
        findings: dict[str, Finding] = {}

        session = await self.session_manager.get_or_create(target)
        client = await self.session_manager.client_for(session)

        async with client:
            context = ProbeContext(
                client=client,
                session=session,
                provider_spec=provider_spec,
                findings=findings,
            )

            for step in self.steps:
                if self.observer:
                    self.observer.on_step_start(step.detector)

                start_time = time.time()

                # 1. Check dependencies
                failed_deps = [
                    req
                    for req in step.requires
                    if req not in findings
                    or findings[req].status in (DetectorStatus.FAILED, DetectorStatus.SKIPPED)
                ]

                if failed_deps:
                    det_cls = DETECTORS.get(step.detector)
                    cost = det_cls.cost if det_cls else DetectorCost.CHEAP
                    finding = Finding(
                        detector=step.detector,
                        category="system",
                        status=DetectorStatus.SKIPPED,
                        cost=cost,
                        confidence=0.0,
                        error=f"Failed dependencies: {', '.join(failed_deps)}",
                    )
                    findings[step.detector] = finding
                    if self.observer:
                        self.observer.on_step_end(
                            StepEvent(
                                detector=step.detector,
                                status=finding.status.value,
                                duration_ms=(time.time() - start_time) * 1000,
                                error=finding.error,
                            )
                        )
                    continue

                # 2. Check custom skip_if logic
                if step.skip_if and step.skip_if(context.model_dump()):
                    continue

                # 3. Execute
                detector_cls = DETECTORS.get(step.detector)
                if not detector_cls:
                    logger.warning(f"Detector {step.detector} not found in registry.")
                    continue

                detector = detector_cls()

                if self.config.skip_expensive and detector.cost == DetectorCost.EXPENSIVE:
                    finding = Finding(
                        detector=step.detector,
                        category=detector.category,
                        status=DetectorStatus.SKIPPED,
                        cost=detector.cost,
                        confidence=0.0,
                        error="Skipped due to --skip-expensive",
                    )
                    findings[step.detector] = finding
                    if self.observer:
                        self.observer.on_step_end(
                            StepEvent(
                                detector=step.detector,
                                status=finding.status.value,
                                duration_ms=(time.time() - start_time) * 1000,
                                error=finding.error,
                            )
                        )
                    continue

                # Inject browser if needed
                if self.config.browser_driver and not self.config.skip_browser:
                    context_dict = context.model_dump()
                    context_dict["browser_driver"] = self.config.browser_driver
                else:
                    context_dict = context.model_dump()

                try:
                    finding = await detector.run(target, context_dict)
                except Exception as exc:
                    finding = Finding(
                        detector=step.detector,
                        category=detector.category,
                        status=DetectorStatus.FAILED,
                        cost=detector.cost,
                        confidence=0.0,
                        error=str(exc),
                    )

                findings[step.detector] = finding

                if self.observer:
                    self.observer.on_step_end(
                        StepEvent(
                            detector=step.detector,
                            status=finding.status.value,
                            duration_ms=(time.time() - start_time) * 1000,
                            error=finding.error,
                        )
                    )

                # Update context for next steps
                if step.detector == "endpoints" and finding.status == DetectorStatus.DETECTED:
                    eps_data = finding.data.get("endpoints", {})
                    context.endpoints = {}
                    for name, e in eps_data.items():
                        # Extraemos solo los campos que espera EndpointInfo
                        context.endpoints[name] = EndpointInfo(
                            path=e.get("path", "/"),
                            method=e.get("method", "GET"),
                            requires_auth=e.get("requires_auth", False),
                            validated=e.get("confidence", 0.0) > 0.8,
                        )

                context.findings = findings

        return findings

    async def assemble_profile(self, target: str, findings: dict[str, Finding]) -> Profile:
        """Map the raw findings into a structured Profile."""
        # (Resto del código igual...)
        transport = TransportInfo(http2=False, tls_fingerprint=None)
        antibot = AntibotInfo(type=AntibotType.NONE, bypass=BypassStrategy.NONE)
        auth = AuthInfo(scheme=AuthScheme.NONE, cookies=[], refresh=BypassStrategy.NONE)
        endpoints: dict[str, EndpointInfo] = {}
        stream_format = StreamFormat.NONE
        tool_calling = False
        schema_compat = SchemaCompat.UNKNOWN
        notes_list = []

        if "transport" in findings and findings["transport"].status == DetectorStatus.DETECTED:
            d = findings["transport"].data
            req_headers = d.get("required_headers", [])
            notes = f"Required headers: {', '.join(req_headers)}" if req_headers else None
            transport = TransportInfo(
                http2=d.get("http2", False),
                tls_fingerprint=d.get("tls_fingerprint"),
                notes=notes,
            )

        if "antibot" in findings and findings["antibot"].status == DetectorStatus.DETECTED:
            d = findings["antibot"].data
            antibot = AntibotInfo(
                type=AntibotType(d.get("type", "unknown")),
                bypass=BypassStrategy(d.get("bypass", "none")),
                impersonate=d.get("impersonate"),
            )

        if "auth" in findings and findings["auth"].status == DetectorStatus.DETECTED:
            d = findings["auth"].data
            auth = AuthInfo(
                scheme=AuthScheme(d.get("scheme", "unknown")),
                cookies=d.get("cookies", []),
                refresh=BypassStrategy(d.get("refresh", "none")),
            )

        if "endpoints" in findings and findings["endpoints"].status == DetectorStatus.DETECTED:
            eps_data = findings["endpoints"].data.get("endpoints", {})
            for name, e in eps_data.items():
                endpoints[name] = EndpointInfo(
                    path=e.get("path", "/"),
                    method=e.get("method", "GET"),
                    requires_auth=e.get("requires_auth", False),
                    validated=e.get("confidence", 0.0) > 0.8,
                )

        if "streaming" in findings and findings["streaming"].status == DetectorStatus.DETECTED:
            d = findings["streaming"].data
            stream_format = StreamFormat(d.get("format", "unknown"))

        if "tools" in findings and findings["tools"].status == DetectorStatus.DETECTED:
            d = findings["tools"].data
            tool_calling = d.get("supported", False)

        if "schema" in findings and findings["schema"].status == DetectorStatus.DETECTED:
            d = findings["schema"].data
            schema_compat = SchemaCompat(d.get("schema_compat", "unknown"))

        for name, f in findings.items():
            if f.status in (DetectorStatus.FAILED, DetectorStatus.SKIPPED):
                notes_list.append(f"{name}: {f.status.value} ({f.error or 'no error'})")

        notes_str = "; ".join(notes_list) if notes_list else None

        return Profile(
            schema_version=CURRENT_SCHEMA_VERSION,
            target=target,
            detected_at=datetime.now(UTC),
            antibot=antibot,
            transport=transport,
            auth=auth,
            endpoints=endpoints,
            stream_format=stream_format,
            tool_calling=tool_calling,
            schema_compat=schema_compat,
            notes=notes_str,
        )
