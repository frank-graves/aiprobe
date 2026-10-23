from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from aiprobe.models.profile import (
    AntibotInfo,
    AntibotType,
    AuthInfo,
    AuthScheme,
    BypassStrategy,
    Profile,
    SchemaCompat,
    StreamFormat,
    TransportInfo,
)


@pytest.fixture
def make_profile() -> Callable[[], Profile]:
    def _make() -> Profile:
        return Profile(
            target="https://example.com",
            detected_at=datetime.now(UTC),
            antibot=AntibotInfo(type=AntibotType.NONE, bypass=BypassStrategy.NONE),
            transport=TransportInfo(http2=False),
            auth=AuthInfo(scheme=AuthScheme.NONE, cookies=[], refresh=BypassStrategy.NONE),
            endpoints={},
            stream_format=StreamFormat.NONE,
            tool_calling=False,
            schema_compat=SchemaCompat.UNKNOWN,
        )

    return _make
