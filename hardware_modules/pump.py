import time
import math 
from comms.wifi_handler import WifiHandler
from comms.serial_handler import SerialHandler



class Pump:
    """Control the peristaltic pump using the 3d printer extruder (Simplified, Handler Agnostic)."""

    
    def __init__(self, comms, mm_per_ml: float = 41.0):
        """
        Initializes the pump controller.

        Args:
            comms (WifiHandler | SerialHandler): The handler instance for sending commands.
            mm_per_ml (float): Calibration factor: mm extruder move per mL pumped.
        """
        # Runtime check for either handler type is still important
        if not isinstance(comms, (WifiHandler, SerialHandler)):
             raise TypeError("Communicator must be an instance of WifiHandler or SerialHandler")
        if not isinstance(mm_per_ml, (int, float)) or mm_per_ml <= 0:
             raise ValueError("mm_per_ml must be a positive number.")

        # Minimal init: Store communicator and calibration
        self.comms = comms
        self.mm_per_ml = float(mm_per_ml)
        # Removed default rate storage, as it's not used when rate is mandatory
        print(f"Pump initialized using {type(self.comms).__name__}: mm_per_ml={self.mm_per_ml}")

    def pump_volume(self, volume_ml: float, flowrate_ml_min: float) -> bool:
        """
        Pumps a specific volume at a specific flowrate.

        Args:
            volume_ml (float): Volume to pump in mL (can be negative).
            flowrate_ml_min (float): Desired flowrate magnitude in mL/min (must be > 0).

        Returns:
            bool: True if commands were sent successfully.
        """
        print(f"\n[{time.strftime('%H:%M:%S')}] Pumping volume: {volume_ml} mL at {flowrate_ml_min} mL/min")

        # Calculate G-code parameters
        distance_mm = volume_ml * self.mm_per_ml
        # Feedrate F must be positive
        feedrate_mm_min = abs(flowrate_ml_min * self.mm_per_ml) # Use abs for safety

        # Avoid sending move if distance is zero
        if math.isclose(distance_mm, 0.0, abs_tol=1e-9):
             print("Warning: Calculated distance is zero, pump will not move.")
             return True # No command needed, consider this success

        print(f"  Calculated: E={distance_mm:.4f} mm, F={feedrate_mm_min:.2f} mm/min")

        # Send commands sequentially
        success = self.comms.send_command("set_extruder_relative")
        if success:
            # Send the move command (E can be negative, F must be positive)
            success = self.comms.send_command("pump_move", E=f"{distance_mm:.4f}", F=f"{feedrate_mm_min:.2f}")

        print(f"[{time.strftime('%H:%M:%S')}] Pump volume finished. Overall Success: {success}")
        return success

    def pump_duration(self, duration_s: float, flowrate_ml_min: float) -> bool:
        """
        Pumps for a specific duration at a specific rate (positive or negative).

        Args:
            duration_s (float): The duration to run the pump in seconds. Must be positive.
            flowrate_ml_min (float): The desired pumping rate in mL/min. Negative pumps backwards.

        Returns:
            bool: True if commands were sent successfully.
        """
        print(f"\n[{time.strftime('%H:%M:%S')}] Pumping duration: {duration_s} s at {flowrate_ml_min} mL/min") # Corrected print


        # Calculate G-code parameters
        # Feedrate F must be positive, based on the magnitude of the rate
        feedrate_mm_min = abs(flowrate_ml_min * self.mm_per_ml)
        # Distance E depends on rate (including sign) and duration
        rate_mm_per_s = (flowrate_ml_min * self.mm_per_ml) / 60.0
        distance_mm = rate_mm_per_s * duration_s

        # Avoid sending move if distance is zero or feedrate is zero
        # Use math.isclose for float comparison
        if math.isclose(distance_mm, 0.0, abs_tol=1e-9) or math.isclose(feedrate_mm_min, 0.0, abs_tol=1e-9):
             print("Warning: Calculated distance or feedrate is zero, pump will not move.")
             return True # No command needed, consider this success

        print(f"  Calculated: E={distance_mm:.4f} mm, F={feedrate_mm_min:.2f} mm/min")

        # Send commands sequentially
        success = self.comms.send_command("set_extruder_relative")
        if success:
            # Send the move command (E can be negative, F must be positive)
            success = self.comms.send_command("pump_move", E=f"{distance_mm:.4f}", F=f"{feedrate_mm_min:.2f}")

        print(f"[{time.strftime('%H:%M:%S')}] Pump duration finished. Overall Success: {success}") # Corrected print
        return success

