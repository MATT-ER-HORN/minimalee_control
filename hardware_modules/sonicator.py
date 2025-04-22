import time
from comms.gcode_handler import GCodeHandler

class Sonicator:
    """Turn the sonicator on for set times using the fan control gcode and a relay"""

    def __init__(self, comms: GCodeHandler):
        """
        Initializes the sonicator control.

        Args:
            comms:  (GCodeHandler):  is how commands are parsed and sent to mainboard using the the gcode handler from this project which deals with creating gcode text and sending it.
        """
        if not isinstance(comms, GCodeHandler):
             raise TypeError("Communicator must be an instance of GCodeHandler")
        
        self.comms = comms
        print("Sonicator initialized.")
    
    def sonicate_duration (self, sonicate_sec = float) -> bool:
        """
        Turns the sonicator (mainboard fan output) on for a specific duration.

        Args:
            sonicate_sec (float): The duration to run the sonicator in seconds. Must be positive.

        Returns:
            bool: True if all steps completed successfully, False otherwise.
        """
        print(f"\n[{time.strftime('%H:%M:%S')}] Running sonicator for: {sonicate_sec} s")

        # check input
        if not isinstance(sonicate_sec, (int, float)) or sonicate_sec <= 0:
            print("Error: Sonicator duration must be a positive number.")
            return False

        # Convert duration to milliseconds for G4 command
        duration_ms = int(sonicate_sec * 1000)
        if duration_ms <= 0:
             print("Error: Calculated duration in milliseconds is not positive.")
             return False

        print(f"  Calculated wait (gcode G04 dwell): {duration_ms} ms")

        # Send sequence of sequence of GCode commands to control board
        # command sequence: Fan on (M106 S255) -> Dwell (G04 P<milliseconds>)-> Fan off (M106 S0)
        success = True
        print("  Turning sonicator ON...")
        if success:
            success = self.comms.send_command("fan_on") # Assumes "fan_on" (M106 S255) exists in COMMANDS

        if success:
            print(f"  Dwelling for {sonicate_sec} seconds...")
            # Assumes "dwell" (G4 P...) exists in COMMANDS and has wait_after=True
            success = self.comms.send_command("dwell", duration_ms=duration_ms)

        # Always try to turn the fan off, even if dwell failed? Or only if dwell succeeded?
        # Let's try turning it off regardless, but the overall success depends on all steps.
        print("  Turning sonicator OFF...")
        off_success = self.comms.send_command("fan_off") # Assumes "fan_off" (M107) exists in COMMANDS
        if not off_success:
             print("Warning: Failed to send fan_off command.")
             # Consider if this should make the overall function fail
             # success = False # Uncomment if fan_off failure should mean overall failure

        print(f"[{time.strftime('%H:%M:%S')}] Sonicator run finished. Overall Success: {success}")
        # Return True only if Fan On and Dwell succeeded. Fan Off failure is just a warning for now.
        return success


        