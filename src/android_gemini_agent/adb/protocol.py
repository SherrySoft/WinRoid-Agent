"""AdbClientProtocol defining abstract interface for ADB operations."""

from typing import List, Optional, Protocol, Tuple, runtime_checkable
from .models import ConnectionResult, DeviceInfo, DeviceState, PairingResult, ShellResult


@runtime_checkable
class AdbClientProtocol(Protocol):
    """Abstract protocol for ADB communication (implemented by RealAdbClient and MockAdbClient)."""

    def connect(self, ip: str, port: int) -> ConnectionResult:
        """Connect to a wireless ADB device via IP and Port."""
        ...

    def disconnect(self, target: Optional[str] = None) -> bool:
        """Disconnect from a specific device or all devices if target is None."""
        ...

    def pair(self, ip: str, port: int, pairing_code: str) -> PairingResult:
        """Pair with an Android 11+ device using ephemeral pairing port and 6-digit code."""
        ...

    def list_devices(self) -> List[DeviceInfo]:
        """List all attached devices and their states."""
        ...

    def get_state(self, device_id: str) -> DeviceState:
        """Get the current state of a device by its serial/target."""
        ...

    def execute_shell(self, device_id: str, command: str, timeout: float = 10.0) -> ShellResult:
        """Execute a shell command on the target device."""
        ...

    def dump_ui_hierarchy(self, device_id: str) -> str:
        """Dump the active UI hierarchy XML from the device."""
        ...

    def get_screen_size(self, device_id: str) -> Tuple[int, int]:
        """Retrieve screen dimensions (width, height) in pixels."""
        ...
