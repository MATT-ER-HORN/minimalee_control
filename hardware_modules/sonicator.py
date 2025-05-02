import time
from comms.wifi_handler import WifiHandler
from comms.serial_handler import SerialHandler

class Sonicator:
    """Control the sonicator using the fan control G-code (Simplified)."""

    # Simplified __init__ - removed type hint and check
    def __init__(self, comms):
        """
        Initializes the Sonicator control.

        Args:
            comms (WifiHandler | SerialHandler): The handler instance for sending commands.
        """
        self.comms = comms
        # Removed print statement

    # Renamed method, removed checks
    def run_for_duration(self, duration_s: float) -> bool:
        """
        Turns the sonicator (fan output) on for a specific duration.

        Args:
            duration_s (float): The duration to run the sonicator in seconds.

        Returns:
            bool: True if commands were sent successfully (minimal check).
        """
        # Calculate milliseconds, assuming duration_s is valid
        duration_ms = int(duration_s * 1000)

        # Send Command Sequence (minimal success checking)
        print(f"\n[{time.strftime('%H:%M:%S')}] Running sonicator for: {duration_s} s")
        print("  Turning sonicator ON...")
        if not self.comms.send_command("fan_on"):
            print("Error sending fan_on command.")
            return False # Exit early on failure

        print(f"  Dwelling for {duration_s} seconds...")
        if not self.comms.send_command("dwell", duration_ms=duration_ms):
            print("Error sending dwell command (or wait failed).")
            # Attempt to turn off fan even if dwell failed
            print("  Attempting to turn sonicator OFF after dwell failure...")
            self.comms.send_command("fan_off")
            return False # Return False as dwell failed

        print("  Turning sonicator OFF...")
        if not self.comms.send_command("fan_off"):
            print("Warning: Failed to send fan_off command, but dwell completed.")
            # Return True because the main action (dwell) seemed to succeed
            # Change to False if fan_off failure is critical
            return True

        print(f"[{time.strftime('%H:%M:%S')}] Sonicator run finished.")
        return True