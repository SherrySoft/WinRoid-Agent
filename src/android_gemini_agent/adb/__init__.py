"""ADB subsystem providing protocol abstractions, client implementations, text escaping, and device control."""

from .client import RealAdbClient
from .controller import DeviceController
from .mock_client import MockAdbClient
from .models import ConnectionResult, DeviceInfo, DeviceState, PairingResult, ShellResult
from .protocol import AdbClientProtocol
from .text_escaper import TextEscaper

__all__ = [
    "DeviceState",
    "DeviceInfo",
    "ConnectionResult",
    "PairingResult",
    "ShellResult",
    "AdbClientProtocol",
    "RealAdbClient",
    "MockAdbClient",
    "TextEscaper",
    "DeviceController",
]
