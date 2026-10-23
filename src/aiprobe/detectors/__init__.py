"""Detectors auto-registration."""

from aiprobe.detectors.antibot import AntibotDetector
from aiprobe.detectors.auth import AuthDetector
from aiprobe.detectors.endpoints import EndpointsDetector
from aiprobe.detectors.schema import SchemaDetector
from aiprobe.detectors.streaming import StreamingDetector
from aiprobe.detectors.tools import ToolsDetector
from aiprobe.detectors.transport import TransportDetector

__all__ = [
    "AntibotDetector",
    "AuthDetector",
    "EndpointsDetector",
    "SchemaDetector",
    "StreamingDetector",
    "ToolsDetector",
    "TransportDetector",
]
