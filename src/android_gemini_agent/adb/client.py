"""Real ADB client implementation interacting with physical or networked Android devices."""

import os
import platform
import re
import shutil
import subprocess
from typing import List, Optional, Tuple

from .models import ConnectionResult, DeviceInfo, DeviceState, PairingResult, ShellResult
from .protocol import AdbClientProtocol


class RealAdbClient(AdbClientProtocol):
    """Client for executing commands via the real ADB binary on the host machine."""

    def __init__(self, adb_path: Optional[str] = None, default_timeout_sec: float = 10.0):
        self.adb_path = self.discover_adb_path(adb_path)
        self.default_timeout_sec = default_timeout_sec

    @classmethod
    def discover_adb_path(cls, explicit_path: Optional[str] = None) -> str:
        """
        Discovers the adb executable path from:
        1. Explicitly provided path argument
        2. ADB_PATH environment variable
        3. Standard SDK paths for Windows, macOS, Linux
        4. System PATH via shutil.which
        """
        if explicit_path and os.path.isfile(explicit_path):
            return explicit_path

        env_adb = os.environ.get("ADB_PATH")
        if env_adb and os.path.isfile(env_adb):
            return env_adb

        system_name = platform.system()
        candidates: List[str] = []

        if system_name == "Windows":
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            user_profile = os.environ.get("USERPROFILE", "")
            program_files = os.environ.get("PROGRAMFILES", "")
            if local_appdata:
                candidates.append(os.path.join(local_appdata, "Android", "Sdk", "platform-tools", "adb.exe"))
            if user_profile:
                candidates.append(os.path.join(user_profile, "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe"))
            if program_files:
                candidates.append(os.path.join(program_files, "Android", "platform-tools", "adb.exe"))
        elif system_name == "Darwin":
            home = os.path.expanduser("~")
            candidates.extend([
                os.path.join(home, "Library", "Android", "sdk", "platform-tools", "adb"),
                "/opt/homebrew/bin/adb",
                "/usr/local/bin/adb",
            ])
        else:  # Linux / other
            home = os.path.expanduser("~")
            candidates.extend([
                os.path.join(home, "Android", "Sdk", "platform-tools", "adb"),
                os.path.join(home, ".android-sdk", "platform-tools", "adb"),
                "/usr/bin/adb",
                "/usr/local/bin/adb",
            ])

        for path in candidates:
            if os.path.isfile(path) and os.access(path, os.X_OK if system_name != "Windows" else os.R_OK):
                return path

        which_path = shutil.which("adb")
        if which_path:
            return which_path

        # Default fallback
        return "adb"

    def _run_adb(self, args: List[str], timeout: float = 10.0) -> Tuple[int, str, str]:
        """Runs an adb command with a strict timeout."""
        cmd = [self.adb_path] + args
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            return process.returncode, process.stdout, process.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Command '{' '.join(cmd)}' timed out after {timeout}s"
        except FileNotFoundError:
            return 127, "", f"ADB executable not found at '{self.adb_path}'"
        except Exception as e:
            return 1, "", str(e)

    def connect(self, ip: str, port: int) -> ConnectionResult:
        """
        Connects to an Android device over Wi-Fi.
        Handles the ADB exit code 0 anomaly on connection failures.
        """
        target = f"{ip}:{port}"
        returncode, stdout, stderr = self._run_adb(["connect", target], timeout=10.0)
        combined = (stdout + "\n" + stderr).strip()
        combined_lower = combined.lower()

        # Success detection
        if "connected to" in combined_lower or "already connected to" in combined_lower:
            return ConnectionResult(
                success=True,
                host=ip,
                port=port,
                message=combined,
                raw_output=combined,
            )

        # Diagnostic classification for failure modes
        if "actively refused" in combined_lower or "connection refused" in combined_lower:
            err = f"Connection refused to {target}. Ensure Wireless Debugging is enabled and port {port} matches the device screen."
        elif "timed out" in combined_lower or "connection timed out" in combined_lower:
            err = f"Connection to {target} timed out. Verify that the device and computer are connected to the same Wi-Fi subnet."
        elif "unauthorized" in combined_lower:
            err = f"Device {target} unauthorized. Check device display and approve the USB/Wireless debugging RSA fingerprint prompt."
        elif "cannot connect to" in combined_lower or "failed to connect to" in combined_lower:
            err = f"Cannot connect to {target}: {combined}"
        else:
            err = combined or f"Failed to connect to {target} (exit code {returncode})"

        return ConnectionResult(
            success=False,
            host=ip,
            port=port,
            error=err,
            raw_output=combined,
        )

    def disconnect(self, target: Optional[str] = None) -> bool:
        """Disconnects a specific device or all devices."""
        args = ["disconnect"]
        if target:
            args.append(target)
        returncode, stdout, stderr = self._run_adb(args, timeout=5.0)
        combined = (stdout + "\n" + stderr).strip().lower()
        return returncode == 0 or "disconnected" in combined

    def pair(self, ip: str, port: int, pairing_code: str) -> PairingResult:
        """
        Pairs with an Android 11+ device using the ephemeral pairing code.
        """
        target = f"{ip}:{port}"
        pairing_code_str = str(pairing_code).strip()
        if not pairing_code_str.isdigit() or len(pairing_code_str) != 6:
            return PairingResult(
                success=False,
                host=ip,
                port=port,
                error=f"Invalid pairing code '{pairing_code_str}'. Android 11+ pairing codes must be exactly 6 digits.",
                raw_output="",
            )

        returncode, stdout, stderr = self._run_adb(["pair", target, pairing_code_str], timeout=10.0)
        combined = (stdout + "\n" + stderr).strip()
        combined_lower = combined.lower()

        if "successfully paired to" in combined_lower:
            return PairingResult(
                success=True,
                host=ip,
                port=port,
                message=combined,
                raw_output=combined,
            )

        if "authentication failed" in combined_lower or "failed" in combined_lower:
            err = f"Pairing authentication failed for {target}. Check that the 6-digit code matches the pairing dialog before it closes."
        elif "protocol fault" in combined_lower:
            err = f"Pairing protocol error with {target}. Keep the pairing dialog open on the device during the pair command."
        else:
            err = combined or f"Pairing failed with {target} (exit code {returncode})"

        return PairingResult(
            success=False,
            host=ip,
            port=port,
            error=err,
            raw_output=combined,
        )

    def list_devices(self) -> List[DeviceInfo]:
        """Lists connected ADB devices with model and state details."""
        returncode, stdout, _ = self._run_adb(["devices", "-l"], timeout=5.0)
        if returncode != 0 or not stdout:
            return []

        devices: List[DeviceInfo] = []
        started_device_list = False

        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("*"):
                continue

            if "List of devices attached" in line:
                started_device_list = True
                continue

            # If header hasn't appeared yet, ignore
            if not started_device_list:
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            serial = parts[0]
            raw_state = parts[1]
            state = DeviceState.from_str(raw_state)
            if state == DeviceState.UNKNOWN:
                continue

            model = "Unknown"
            product = "Unknown"
            transport_id = ""

            for part in parts[2:]:
                if part.startswith("model:"):
                    model = part.split(":", 1)[1]
                elif part.startswith("product:"):
                    product = part.split(":", 1)[1]
                elif part.startswith("transport_id:"):
                    transport_id = part.split(":", 1)[1]

            devices.append(
                DeviceInfo(
                    serial=serial,
                    state=state,
                    model=model,
                    product=product,
                    transport_id=transport_id,
                )
            )

        return devices

    def get_state(self, device_id: str) -> DeviceState:
        """Queries the connection state of a specific device."""
        returncode, stdout, stderr = self._run_adb(["-s", device_id, "get-state"], timeout=3.0)
        combined = (stdout + "\n" + stderr).strip().lower()

        if returncode == 0 and "device" in combined:
            return DeviceState.CONNECTED
        elif "offline" in combined:
            return DeviceState.OFFLINE
        elif "unauthorized" in combined:
            return DeviceState.UNAUTHORIZED
        elif "not found" in combined or "no such device" in combined or returncode != 0:
            return DeviceState.DISCONNECTED

        return DeviceState.UNKNOWN

    def execute_shell(self, device_id: str, command: str, timeout: float = 10.0) -> ShellResult:
        """Executes a shell command on the target device."""
        returncode, stdout, stderr = self._run_adb(["-s", device_id, "shell", command], timeout=timeout)
        return ShellResult(exit_code=returncode, stdout=stdout, stderr=stderr)

    def dump_ui_hierarchy(self, device_id: str) -> str:
        """
        Dumps the UI hierarchy XML from the device.
        Uses a compound single shell execution to minimize round trips.
        """
        temp_path = "/data/local/tmp/window_dump.xml"
        cmd = f"uiautomator dump {temp_path} >/dev/null 2>&1 && cat {temp_path} && rm -f {temp_path}"
        result = self.execute_shell(device_id, cmd, timeout=15.0)

        output = result.stdout.strip()
        if "<hierarchy" in output:
            # Extract clean XML hierarchy
            start_idx = output.find("<hierarchy")
            end_idx = output.rfind("</hierarchy>")
            if start_idx != -1 and end_idx != -1:
                return output[start_idx : end_idx + len("</hierarchy>")]
            return output

        # Secondary fallback: dump to /sdcard/window_dump.xml
        sdcard_cmd = "uiautomator dump /sdcard/window_dump.xml >/dev/null 2>&1 && cat /sdcard/window_dump.xml && rm -f /sdcard/window_dump.xml"
        fallback_res = self.execute_shell(device_id, sdcard_cmd, timeout=15.0)
        fb_output = fallback_res.stdout.strip()
        if "<hierarchy" in fb_output:
            start_idx = fb_output.find("<hierarchy")
            end_idx = fb_output.rfind("</hierarchy>")
            if start_idx != -1 and end_idx != -1:
                return fb_output[start_idx : end_idx + len("</hierarchy>")]
            return fb_output

        return ""

    def get_screen_size(self, device_id: str) -> Tuple[int, int]:
        """Queries physical or override screen dimensions via 'wm size'."""
        res = self.execute_shell(device_id, "wm size", timeout=5.0)
        output = res.stdout + "\n" + res.stderr

        # Check for Override size first, then Physical size
        override_match = re.search(r"Override size:\s*(\d+)x(\d+)", output)
        if override_match:
            return int(override_match.group(1)), int(override_match.group(2))

        phys_match = re.search(r"Physical size:\s*(\d+)x(\d+)", output)
        if phys_match:
            return int(phys_match.group(1)), int(phys_match.group(2))

        # Default fallback
        return 1080, 2400
