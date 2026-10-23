"""Offline tests for the validate drift logic. (Extracting logic for testability)."""

from __future__ import annotations

from aiprobe.models.profile import EndpointInfo, Profile


def compare_profiles(old: Profile, new: Profile) -> list[str]:
    """Helper mirroring the validate command logic to test it easily."""
    drift = []
    if old.transport.http2 != new.transport.http2:
        drift.append("http2 changed")
    if old.antibot.type != new.antibot.type:
        drift.append("antibot type changed")

    for name in set(old.endpoints.keys()) | set(new.endpoints.keys()):
        old_ep = old.endpoints.get(name)
        new_ep = new.endpoints.get(name)

        if old_ep and not new_ep:
            drift.append(f"Endpoint '{name}' removed.")
        elif not old_ep and new_ep:
            drift.append(f"Endpoint '{name}' added.")
        elif old_ep and new_ep:
            if old_ep.path != new_ep.path or old_ep.method != new_ep.method:
                drift.append(f"Endpoint '{name}' changed.")
            if old_ep.requires_auth != new_ep.requires_auth:
                drift.append(f"Endpoint '{name}' auth changed.")
    return drift


def test_no_drift(make_profile) -> None:
    old = make_profile()
    new = make_profile()
    assert len(compare_profiles(old, new)) == 0


def test_drift_endpoint_added(make_profile) -> None:
    old = make_profile()
    new = make_profile()
    new.endpoints["chat"] = EndpointInfo(
        path="/chat", method="POST", requires_auth=False, validated=True
    )

    drift = compare_profiles(old, new)
    assert len(drift) == 1
    assert "added" in drift[0]


def test_drift_endpoint_removed(make_profile) -> None:
    old = make_profile()
    old.endpoints["chat"] = EndpointInfo(
        path="/chat", method="POST", requires_auth=False, validated=True
    )
    new = make_profile()

    drift = compare_profiles(old, new)
    assert len(drift) == 1
    assert "removed" in drift[0]
