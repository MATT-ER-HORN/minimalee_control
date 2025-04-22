import time
# Import looks okay, assuming 'comms' folder and 'gcode_handler' module with 'GCodeHandler' class
from comms.gcode_handler import GCodeHandler

class Pump:
    """contol the peristaltic pump using the 3d printer extruder""" # Typo: contol -> control

    # Init signature looks okay, uses mL/min for default rate.
    def __init__(self, comms: GCodeHandler, mm_per_ml: float = 1.0, default_rate_ml_min: float = 5):
        """
        Initializes the pump controller. # Typo: Initializes -> Initializes

        Args:
            comms:  GCodeHandler is how the pump sends commands using the the gcode handler from this project which deals with creating gcode text and sending it. # Formatting inconsistent
            mm_per_ml (float): calibrates the mm of the extruder motor should extrude per ml of solvent.this is an artifact of the pump being driven by a 3d printer control so I decided to keep the feedrate in mm # Formatting inconsistent, sentence structure.
            default_rate_ml_min (float): default flowrate if the flowrate is given as zero # Description slightly inaccurate - it's used if flowrate is None.
        """
        # Type checking for comms and mm_per_ml is good.
        if not isinstance(comms, GCodeHandler):
            raise TypeError("Communicator must be an instance of GCodeHandler")
        # Missing check for mm_per_ml > 0
        if not isinstance(mm_per_ml, (int, float)):
            raise ValueError("mm_per_ml must be a number.")
        # Missing check for default_rate_ml_min > 0

        self.comms = comms # Stores communicator instance, good.
        self.mm_per_ml = float(mm_per_ml)
        self.default_rate_ml_min = float(default_rate_ml_min)

        print(f"Pump initialized, default flow rate (mL/min): {self.default_rate_ml_min}")

    # Signature okay, uses mL/min
    def pump_volume(self, volume_ml: float, flowrate_ml_min: float | None = None) -> bool:
        """
        Pumps a specific volume at a given flowrate - flowrate is default if none is given

        Args:
            volume_ml (float): Volume to pump in mL
            flowrate_ml_min: (float | None, optional): desired flowrate in mL/min. defaults to default_rate_ml_min # Needs standard type hint format

        Returns:
            bool: True if all steps complete successfully
        """
        # Handles default rate correctly.
        set_rate = flowrate_ml_min if flowrate_ml_min is not None else self.default_rate_ml_min
        print(f"\n[{time.strftime('%H:%M:%S')}] Pumping volume: {volume_ml} mL at {set_rate} mL/min")

        # Input Validation - VOLUME: Logic error, allows negatives. Should check > 0 (or >= 0 if zero allowed)
        if not isinstance(volume_ml, (float, int)) or volume_ml < 50.0 or volume_ml > -50.0 : # <<< LOGIC ERROR
            print("Error: Volume must be a number between -50 and 50 mL") # Message doesn't match logic, and negative pumping was requested before. Let's assume positive for now unless user clarifies again. Should be `volume_ml <= 0`.
            return False
        # Input Validation - FLOWRATE: Logic error, allows negatives. Checks wrong variable. Should check `set_rate > 0`.
        if not isinstance(flowrate_ml_min, (float, int)) or flowrate_ml_min < 20.0 or flowrate_ml_min > -20.0 : # <<< LOGIC ERROR & WRONG VARIABLE
            print("Error: Flowrate must be a number between -20 and 20 mL\min") # Message doesn't match logic. Should be `set_rate <= 0`.
            return False

        # Calculation
        distance_mm = volume_ml * self.mm_per_ml
        # Calculation Error: Needs self.mm_per_ml
        feedrate_mm_min = set_rate * self.mm_per_ml # <<< CORRECTED: was mm_per_ml

        # Checks
        # Hardcoded limit. Missing return False.
        if feedrate_mm_min > 400: # <<< Hardcoded, missing return
            print("Error: Check flow rate too high")
            return False # <<< Added return
        # Add check for feedrate <= 0
        if feedrate_mm_min <= 0:
            print(f"Error: Calculated non-positive feedrate ({feedrate_mm_min:.2f}). Check inputs and mm_per_ml.")
            return False
        # Add check for distance == 0
        if abs(distance_mm) < 1e-9: # Use tolerance for float comparison
             print("Warning: Calculated distance is zero. Pump will not move.")
             return True # Treat as success (no move needed)


        # Send commands - uses self.comms correctly.
        success = self.comms.send_command("set_extruder_relative")
        if success:
            success = self.comms.send_command("pump_move", E=f"{distance_mm:.4f}",F=f"{feedrate_mm_min:.2f}")
        print(f"[{time.strftime('%H:%M:%S')}] Pump volume finished. Overall Success: {success}")
        return success

    # pump_duration method started but not finished
    def pump_duration(self, duration_s: float, flowrate_ml_min: float | None = None) -> bool: # Changed flowrate param name for consistency
        """
        Pumps for a specific duration at a given rate.
        Uses the default rate if flowrate_ml_min is None.

        Args:
            duration_s (float): The duration to run the pump in seconds. Must be positive.
            flowrate_ml_min (float | None, optional): The desired pumping rate in mL/min.
                                                      Negative value pumps backwards.
                                                      Defaults to default_rate_ml_min.

        Returns:
            bool: True if all steps completed successfully, False otherwise.
        """
        set_rate = flowrate_ml_min if flowrate_ml_min is not None else self.default_rate_ml_min
        # Typo in print statement: duration units are 's' not 'mL'
        print(f"\n[{time.strftime('%H:%M:%S')}] Pumping duration: {duration_s} s at {set_rate} mL/min") # <<< Corrected unit

        # Input checks
        if not isinstance(duration_s, (int, float)) or duration_s <= 0:
            print("Error: Duration must be a positive number.")
            return False
        # Check for non-numeric rate needed
        if not isinstance(set_rate, (int, float)): # <<< Added check
            print(f"Error: Rate ({set_rate}) must be a number.")
            return False
        # Allow zero rate? If so, distance will be zero.
        # if set_rate == 0.0:
        #      print("Warning: Rate is zero. Pump will not move.")
        #      return True


        # Calculate G-code parameters
        # Feedrate F must be positive, based on the magnitude of the rate
        feedrate_mm_min = abs(set_rate * self.mm_per_ml)
        # Distance E depends on rate (including sign) and duration
        rate_mm_per_s = (set_rate * self.mm_per_ml) / 60.0
        distance_mm = rate_mm_per_s * duration_s

        # Checks
        # Check feedrate magnitude against max
        if feedrate_mm_min > 400: # <<< Hardcoded limit
            print(f"Error: Calculated feedrate magnitude ({feedrate_mm_min:.2f} mm/min) exceeds maximum (400).") # Use configured max?
            return False
        # Check if distance is zero (can happen if rate is zero)
        if abs(distance_mm) < 1e-9 and duration_s > 0:
             print("Warning: Calculated distance is zero (rate might be zero). Pump will not move.")
             return True
        # Check if feedrate is zero when distance isn't (shouldn't happen if rate=0 handled above)
        if abs(distance_mm) > 1e-9 and feedrate_mm_min <= 0:
             print(f"Error: Calculated non-positive feedrate ({feedrate_mm_min:.2f}) for non-zero distance.")
             return False

        print(f"  Calculated: E={distance_mm:.4f} mm, F={feedrate_mm_min:.2f} mm/min")

        # Send commands
        success = self.comms.send_command("set_extruder_relative")
        if success:
            success = self.comms.send_command("pump_move", E=f"{distance_mm:.4f}",F=f"{feedrate_mm_min:.2f}")
        # Typo in print statement: Pump volume -> Pump duration
        print(f"[{time.strftime('%H:%M:%S')}] Pump duration finished. Overall Success: {success}") # <<< Corrected text
        return success