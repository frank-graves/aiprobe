"""Declarative anti-bot signatures.

To add a new anti-bot system, add a new `AntibotSignature` entry to
`ANTIBOT_SIGNATURES`. The detector will automatically pick it up.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aiprobe.models.profile import AntibotType


@dataclass(frozen=True)
class AntibotSignature:
    """Declarative fingerprint for a specific anti-bot provider."""

    name: AntibotType
    header_keys: list[str] = field(default_factory=list)
    header_patterns: list[str] = field(default_factory=list)
    body_substrings: list[str] = field(default_factory=list)
    cookie_names: list[str] = field(default_factory=list)
    status_codes: list[int] = field(default_factory=list)
    weight: float = 0.5
    is_js_challenge: bool = False
    requires_browser: bool = False


ANTIBOT_SIGNATURES: list[AntibotSignature] = [
    AntibotSignature(
        name=AntibotType.CF_TLS,
        header_keys=["cf-ray", "cf-mitigated"],
        header_patterns=[],
        body_substrings=[],
        cookie_names=[],
        status_codes=[403, 503],
        weight=0.6,
        is_js_challenge=False,
        requires_browser=False,
    ),
    AntibotSignature(
        name=AntibotType.CF_JS,
        header_keys=["cf-ray"],
        header_patterns=[],
        body_substrings=[
            "Just a moment",
            "Checking your browser",
            "cf-challenge-running",
            "/cdn-cgi/challenge-platform/",
            "__cf_chl_",
        ],
        cookie_names=["__cf_bm"],
        status_codes=[403, 503],
        weight=0.7,
        is_js_challenge=True,
        requires_browser=True,
    ),
    AntibotSignature(
        name=AntibotType.TURNSTILE,
        header_keys=[],
        header_patterns=[],
        body_substrings=[
            "challenges.cloudflare.com/turnstile",
            "cf-turnstile",
        ],
        cookie_names=["cf_clearance"],
        status_codes=[403],
        weight=0.8,
        is_js_challenge=True,
        requires_browser=True,
    ),
    AntibotSignature(
        name=AntibotType.DATADOME,
        header_keys=["x-datadome"],
        header_patterns=[],
        body_substrings=[],
        cookie_names=["datadome", "dd_cookie_test_"],
        status_codes=[403],
        weight=0.8,
        is_js_challenge=True,
        requires_browser=True,
    ),
    AntibotSignature(
        name=AntibotType.UNKNOWN,  # Placeholder for Akamai, see note below
        header_keys=[],
        header_patterns=[r"akamai-.*"],
        body_substrings=[],
        cookie_names=["_abck", "bm_sz", "ak_bmsc"],
        status_codes=[403],
        weight=0.7,
        is_js_challenge=False,
        requires_browser=False,
    ),
    AntibotSignature(
        name=AntibotType.UNKNOWN,  # PerimeterX
        header_keys=[],
        header_patterns=[r"x-px-.*"],
        body_substrings=[],
        cookie_names=["_px", "_pxhd"],
        status_codes=[403],
        weight=0.7,
        is_js_challenge=False,
        requires_browser=False,
    ),
    AntibotSignature(
        name=AntibotType.UNKNOWN,  # Imperva/Incapsula
        header_keys=["x-iinfo"],
        header_patterns=[],
        body_substrings=["Incapsula incident ID"],
        cookie_names=[],  # Matched via regex in detector for incap_ses_*
        status_codes=[403],
        weight=0.7,
        is_js_challenge=False,
        requires_browser=False,
    ),
]
