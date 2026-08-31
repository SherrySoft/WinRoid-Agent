"""Data models and type definitions for ADB subsystem."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DeviceState(str, Enum):
    """Represents the connection state of an Android device."""
    CONNECTED = "device"
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"

    @classmethod
    def from_str(cls, state_str: str) -> "DeviceState":
        """Parse state string safely."""
        cleaned = state_str.strip().lower()
        for member in cls:
            if member.value == cleaned:
                return member
        return cls.UNKNOWN


@dataclass
class DeviceInfo:
    """Information about an attached Android device."""
    serial: str
    state: DeviceState = DeviceState.UNKNOWN
    model: str = "Unknown"
    product: str = "Unknown"
    transport_id: str = ""


@dataclass
class ConnectionResult:
    """Result of a wireless ADB connect attempt."""
    success: bool
    host: str = ""
    port: int = 5555
    message: str = ""
    error: str = ""
    raw_output: str = ""


@dataclass
class PairingResult:
    """Result of an Android 11+ pairing attempt."""
    success: bool
    host: str = ""
    port: int = 5555
    message: str = ""
    error: str = ""
    raw_output: str = ""


@dataclass
class ShellResult:
    """Result of an ADB shell command execution."""
    exit_code: int
    stdout: str = ""
    stderr: str = ""

    @property
    def output(self) -> str:
        """Combined stdout and stderr formatted as a single string."""
        if self.stdout and self.stderr:
            return f"{self.stdout}\n{self.stderr}".strip()
        elif self.stdout:
            return self.stdout.strip()
        elif self.stderr:
            return self.stderr.strip()
        return ""
