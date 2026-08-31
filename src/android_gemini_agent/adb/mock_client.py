"""Mock ADB client implementation for offline unit, integration, and E2E testing."""

from typing import Any, Dict, List, Optional, Tuple

from .models import ConnectionResult, DeviceInfo, DeviceState, PairingResult, ShellResult
from .protocol import AdbClientProtocol


DEFAULT_MOCK_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.android.settings" bounds="[0,0][1080,2400]" clickable="false">
    <node index="0" text="Settings" resource-id="com.android.settings:id/homepage_title" class="android.widget.TextView" package="com.android.settings" bounds="[60,140][900,240]" clickable="false"/>
    <node index="1" text="Search settings" resource-id="com.android.settings:id/search_action_bar" class="android.widget.EditText" package="com.android.settings" bounds="[40,260][1040,380]" clickable="true"/>
    <node index="2" text="Network &amp; internet" resource-id="android:id/title" class="android.widget.TextView" package="com.android.settings" bounds="[180,440][980,520]" clickable="true"/>
    <node index="3" text="Display" resource-id="android:id/title" class="android.widget.TextView" package="com.android.settings" bounds="[180,560][980,640]" clickable="true"/>
    <node index="4" text="Battery" resource-id="android:id/title" class="android.widget.TextView" package="com.android.settings" bounds="[180,680][980,760]" clickable="true"/>
  </node>
</hierarchy>"""


class MockAdbClient(AdbClientProtocol):
    """
    In-memory simulation of ADB server and device transport.
    Tracks commands, mimics shell outputs, simulates network drops, and serves XML hierarchy fixtures.
    """

    def __init__(self):
        self.devices: Dict[str, DeviceInfo] = {}
        self.paired_endpoints: Dict[str, str] = {}
        self.history: List[Dict[str, Any]] = []
        self.xml_fixtures: Dict[str, str] = {
            "default": DEFAULT_MOCK_XML,
        }
        self.current_xml_key: str = "default"
        self.screen_size: Tuple[int, int] = (1080, 2400)
        self.fail_next_command: Optional[str] = None
        self.simulate_disconnect_after_actions: int = 0
        self.action_counter: int = 0

    def connect(self, ip: str, port: int) -> ConnectionResult:
        """Simulates wireless adb connect."""
        target = f"{ip}:{port}"
        self.history.append({"action": "connect", "ip": ip, "port": port, "target": target})

        if self.fail_next_command == "connect":
            self.fail_next_command = None
            return ConnectionResult(
                success=False,
                host=ip,
                port=port,
                error=f"Connection refused to {target}. Target actively refused connection.",
                raw_output=f"cannot connect to {target}: No connection could be made",
            )

        dev = DeviceInfo(
            serial=target,
            state=DeviceState.CONNECTED,
            model="MockPixel7",
            product="panther",
            transport_id="1",
        )
        self.devices[target] = dev
        return ConnectionResult(
            success=True,
            host=ip,
            port=port,
            message=f"connected to {target}",
            raw_output=f"connected to {target}",
        )

    def disconnect(self, target: Optional[str] = None) -> bool:
        """Simulates wireless adb disconnect."""
        self.history.append({"action": "disconnect", "target": target})
        if target:
            self.devices.pop(target, None)
        else:
            self.devices.clear()
        return True

    def pair(self, ip: str, port: int, pairing_code: str) -> PairingResult:
        """Simulates Android 11+ adb pair."""
        target = f"{ip}:{port}"
        code_str = str(pairing_code).strip()
        self.history.append({"action": "pair", "ip": ip, "port": port, "target": target, "code": code_str})

        if self.fail_next_command == "pair":
            self.fail_next_command = None
            return PairingResult(
                success=False,
                host=ip,
                port=port,
                error=f"Pairing authentication failed for {target}.",
                raw_output="Failed: Authentication failed",
            )

        if len(code_str) != 6 or not code_str.isdigit():
            return PairingResult(
                success=False,
                host=ip,
                port=port,
                error=f"Invalid pairing code '{code_str}'. Android 11+ pairing codes must be 6 digits.",
                raw_output="Failed: Invalid code format",
            )

        self.paired_endpoints[target] = code_str
        return PairingResult(
            success=True,
            host=ip,
            port=port,
            message=f"Successfully paired to {target} [guid=mock-guid-12345]",
            raw_output=f"Successfully paired to {target} [guid=mock-guid-12345]",
        )

    def list_devices(self) -> List[DeviceInfo]:
        """Lists active simulated devices."""
        return list(self.devices.values())

    def get_state(self, device_id: str) -> DeviceState:
        """Gets device state or DISCONNECTED if not present."""
        if device_id not in self.devices:
            return DeviceState.DISCONNECTED
        return self.devices[device_id].state

    def execute_shell(self, device_id: str, command: str, timeout: float = 10.0) -> ShellResult:
        """Simulates shell execution on the target device."""
        self.action_counter += 1
        self.history.append({
            "action": "shell",
            "device_id": device_id,
            "command": command,
            "timeout": timeout,
            "step": self.action_counter,
        })

        if self.fail_next_command == "shell":
            self.fail_next_command = None
            return ShellResult(exit_code=1, stdout="", stderr="error: shell command execution failed")

        # Simulate Wi-Fi drop if action limit reached
        if self.simulate_disconnect_after_actions > 0 and self.action_counter >= self.simulate_disconnect_after_actions:
            self.devices.pop(device_id, None)
            return ShellResult(exit_code=1, stdout="", stderr=f"error: device '{device_id}' not found")

        if device_id not in self.devices or self.devices[device_id].state != DeviceState.CONNECTED:
            return ShellResult(exit_code=1, stdout="", stderr=f"error: device '{device_id}' not found")

        # Command parsing & mock response synthesis
        if command.startswith("monkey -p"):
            parts = command.split()
            pkg = parts[2] if len(parts) > 2 else "unknown"
            if pkg == "nonexistent.package":
                return ShellResult(exit_code=1, stdout="** No activities found to run", stderr="")
            return ShellResult(exit_code=0, stdout="Events injected: 1\n## Network stats: elapsed time=12ms", stderr="")

        elif command.startswith("am start"):
            return ShellResult(exit_code=0, stdout="Starting: Intent { act=android.intent.action.MAIN }", stderr="")

        elif command.startswith("input tap"):
            return ShellResult(exit_code=0, stdout="", stderr="")

        elif command.startswith("input swipe"):
            return ShellResult(exit_code=0, stdout="", stderr="")

        elif command.startswith("input keyevent"):
            return ShellResult(exit_code=0, stdout="", stderr="")

        elif command.startswith("input text"):
            return ShellResult(exit_code=0, stdout="", stderr="")

        elif "cmd clipboard" in command:
            return ShellResult(exit_code=0, stdout="", stderr="")

        elif "wm size" in command:
            return ShellResult(exit_code=0, stdout=f"Physical size: {self.screen_size[0]}x{self.screen_size[1]}", stderr="")

        elif "uiautomator dump" in command:
            xml = self.xml_fixtures.get(self.current_xml_key, self.xml_fixtures["default"])
            return ShellResult(exit_code=0, stdout=xml, stderr="")

        return ShellResult(exit_code=0, stdout="OK", stderr="")

    def dump_ui_hierarchy(self, device_id: str) -> str:
        """Returns the simulated active screen XML hierarchy."""
        self.history.append({"action": "dump_ui_hierarchy", "device_id": device_id})

        if self.fail_next_command == "dump_ui_hierarchy":
            self.fail_next_command = None
            return ""

        if device_id not in self.devices or self.devices[device_id].state != DeviceState.CONNECTED:
            return ""

        return self.xml_fixtures.get(self.current_xml_key, self.xml_fixtures.get("default", ""))

    def get_screen_size(self, device_id: str) -> Tuple[int, int]:
        """Returns mock screen dimensions."""
        return self.screen_size

    # Test Helper Methods
    def set_fixture(self, key: str, xml_content: str) -> None:
        """Register a named XML hierarchy fixture."""
        self.xml_fixtures[key] = xml_content

    def switch_fixture(self, key: str) -> None:
        """Switch the current active screen fixture."""
        if key in self.xml_fixtures:
            self.current_xml_key = key

    def set_device_state(self, serial: str, state: DeviceState) -> None:
        """Manually mutate a device state for testing."""
        if serial in self.devices:
            self.devices[serial].state = state
        else:
            self.devices[serial] = DeviceInfo(serial=serial, state=state)

    def clear_history(self) -> None:
        """Clear recorded command history."""
        self.history.clear()

    def reset(self) -> None:
        """Reset mock client state completely."""
        self.devices.clear()
        self.paired_endpoints.clear()
        self.history.clear()
        self.fail_next_command = None
        self.simulate_disconnect_after_actions = 0
        self.action_counter = 0
        self.current_xml_key = "default"
