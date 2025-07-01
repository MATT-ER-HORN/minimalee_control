import time
import math 
from comms.wifi_handler import WifiHandler
from comms.serial_handler import SerialHandler


class Hotplate:
    """Control the hotplate using the 3d printer hotbed (Simplified, Handler Agnostic)."""

    
    def __init__(self, comms, max_temp: float = 150.0):
        """
        Initializes the hotplate controller.

        Args:
            comms (WifiHandler | SerialHandler): The handler instance for sending commands.
            max_temp (float): Maximum safe temperature in Celsius for safety checks.
        """
        # Runtime check for either handler type is still important
        if not isinstance(comms, (WifiHandler, SerialHandler)):
             raise TypeError("Communicator must be an instance of WifiHandler or SerialHandler")
        if not isinstance(max_temp, (int, float)) or max_temp <= 0:
             raise ValueError("max_temp must be a positive number.")

        # Minimal init: Store communicator and max temperature
        self.comms = comms
        self.max_temp = float(max_temp)
        self.current_target = 0.0  # Track current target temperature
        print(f"Hotplate initialized using {type(self.comms).__name__}: max_temp={self.max_temp}°C")

    def set_temperature(self, target_temp: float) -> bool:
        """
        Sets the hotplate to a specific temperature.

        Args:
            target_temp (float): Target temperature in Celsius.

        Returns:
            bool: True if commands were sent successfully.
        """
        print(f"\n[{time.strftime('%H:%M:%S')}] Setting hotplate temperature: {target_temp}°C")

        # Safety check for temperature limits
        if target_temp < 0:
            print("Warning: Target temperature cannot be negative. Setting to 0°C.")
            target_temp = 0.0
        elif target_temp > self.max_temp:
            print(f"Warning: Target temperature {target_temp}°C exceeds maximum {self.max_temp}°C. Limiting to maximum.")
            target_temp = self.max_temp

        # Update current target
        self.current_target = target_temp

        # Send hotbed temperature command
        success = self.comms.send_command("set_bed_temp", S=f"{target_temp:.1f}")

        if success:
            print(f"[{time.strftime('%H:%M:%S')}] Hotplate temperature set to {target_temp}°C")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Failed to set hotplate temperature")
        
        return success

    def heat_and_wait(self, target_temp: float, timeout_s: float = 600.0) -> bool:
        """
        Sets temperature and waits for the hotplate to reach target temperature.

        Args:
            target_temp (float): Target temperature in Celsius.
            timeout_s (float): Maximum time to wait in seconds (default 10 minutes).

        Returns:
            bool: True if commands were sent successfully.
        """
        print(f"\n[{time.strftime('%H:%M:%S')}] Heating hotplate to {target_temp}°C and waiting...")

        # Safety check for temperature limits
        if target_temp < 0:
            print("Warning: Target temperature cannot be negative. Setting to 0°C.")
            target_temp = 0.0
        elif target_temp > self.max_temp:
            print(f"Warning: Target temperature {target_temp}°C exceeds maximum {self.max_temp}°C. Limiting to maximum.")
            target_temp = self.max_temp

        # Update current target
        self.current_target = target_temp

        # Send hotbed temperature and wait command
        success = self.comms.send_command("set_bed_temp_wait", S=f"{target_temp:.1f}")

        if success:
            print(f"[{time.strftime('%H:%M:%S')}] Hotplate heating to {target_temp}°C with wait command sent")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Failed to send heat and wait command")
        
        return success

    def turn_off(self) -> bool:
        """
        Turns off the hotplate by setting temperature to 0.

        Returns:
            bool: True if commands were sent successfully.
        """
        print(f"\n[{time.strftime('%H:%M:%S')}] Turning off hotplate")

        # Set target to 0
        self.current_target = 0.0

        # Send command to turn off hotbed
        success = self.comms.send_command("set_bed_temp", S="0")

        if success:
            print(f"[{time.strftime('%H:%M:%S')}] Hotplate turned off")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Failed to turn off hotplate")
        
        return success

    def get_temperature(self) -> bool:
        """
        Requests current temperature from the hotplate.

        Returns:
            bool: True if command was sent successfully.
        """
        print(f"\n[{time.strftime('%H:%M:%S')}] Requesting hotplate temperature")

        # Send temperature report command
        success = self.comms.send_command("get_temp")

        if success:
            print(f"[{time.strftime('%H:%M:%S')}] Temperature request sent")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Failed to request temperature")
        
        return success

    def get_current_target(self) -> float:
        """
        Returns the current target temperature.

        Returns:
            float: Current target temperature in Celsius.
        """
        return self.current_target

    def is_heating(self) -> bool:
        """
        Checks if the hotplate is currently set to heat (target > 0).

        Returns:
            bool: True if target temperature is greater than 0.
        """
        return self.current_target > 0.0