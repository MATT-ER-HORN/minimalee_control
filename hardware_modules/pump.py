import time
from comms.gcode_handler import GCodeHandler

class Pump:
    """control the peristaltic pump using the 3d printer extruder"""

    def __init__(self, comms: GCodeHandler, mm_per_ml: float = 1.0, default_rate_ml_min: float = 5):
        """
        Initializes the pump controller.

        Args:
            comms:  GCodeHandler is how the pump sends commands using the the gcode handler from this project which deals with creating gcode text and sending it.
            mm_per_ml (float): calibrates the mm of the extruder motor should extrude per ml of solvent.this is an artifact of the pump being driven by a 3d printer control so I decided to keep the feedrate in mm
            default_rate_ml_min (float): default flowrate if the flowrate is given as zero
        """
        if not isinstance(comms, GCodeHandler):
             raise TypeError("Communicator must be an instance of GCodeHandler")
        if not isinstance(mm_per_ml, (int, float)):
             raise ValueError("mm_per_ml must be a number.")

        self.comms = comms
        self.mm_per_ml = float(mm_per_ml)
        self.default_rate_ml_min = float(default_rate_ml_min)

        print(f"Pump initialized, default flow rate (mL/min): {self.default_rate_ml_min}")        

    def pump_volume(self, volume_ml: float, flowrate_ml_min: float | None = None) -> bool:
            """
            Pumps a specific volume at a given flowrate - flowrate is default if none is given

            Args:
                volume_ml (float): Volume to pump in mL
                flowrate_ml_min: (float | None, optional): desired flowrate in mL/min. defaults to default_rate_ml_min

            Returns:
                bool: True if all steps complete successfully     
            """ 
            set_rate = flowrate_ml_min if flowrate_ml_min is not None else self.default_rate_ml_min
            print(f"\n[{time.strftime('%H:%M:%S')}] Pumping volume: {volume_ml} mL at {set_rate} mL/min")

            if not isinstance(volume_ml, (float, int)) or volume_ml < -50.0 or volume_ml > 50.0 :
                print("Error: Volume must be a number between -50 and 50 mL")
                return False
            if not isinstance(flowrate_ml_min, (float, int)) or flowrate_ml_min < -80.0 or flowrate_ml_min > 80.0 :
                print("Error: Flowrate must be a number between -20 and 20 mL\min")
                return False
            
            #calculate extruder distance in mm from volume_ml and feedrate in mm/sec from set_rate
            distance_mm = volume_ml * self.mm_per_ml
            feedrate_mm_min = set_rate * self.mm_per_ml

            #checks:
            if feedrate_mm_min > 400:
                print("Error: Check flow rate too high")
            # ToDo: more checks

            #Send commands sequentially to mainboard using gcode handler and check complete (True) between each step
            success = self.comms.send_command("set_extruder_relative")
            if success:
                success = self.comms.send_command("pump_move", E=f"{distance_mm:0.4f}",F=f"{feedrate_mm_min:.2f}")
            print(f"[{time.strftime('%H:%M:%S')}] Pump volume finished. Overall Success: {success}")
            return success

    def pump_duration(self, duration_s: float, flowrate_ml_min: float | None = None) -> bool:
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
            print(f"\n[{time.strftime('%H:%M:%S')}] Pumping duration: {duration_s} mL at {set_rate} mL/min")

            #input checks
            if not isinstance(duration_s, (int, float)) or duration_s <= 0:
                print("Error: Duration must be a positive number.")
                return False
            if not isinstance(set_rate, (int, float)):
                print(f"Error: Rate ({set_rate}) must be a number.")
                return False
            
            #calculate extruder distance in mm from duration and feedrate in mm/sec from set_rate
            # Feedrate F must be positive, based on the magnitude of the rate
            feedrate_mm_min = abs(set_rate * self.mm_per_ml)
            # Distance E depends on rate (including sign) and duration
            rate_mm_per_s = (set_rate * self.mm_per_ml) / 60.0
            distance_mm = rate_mm_per_s * duration_s

            #checks:
            if feedrate_mm_min > 400:
                print("Error: Check flow rate too high")
            # ToDo: more checks

            print(f"  Calculated: E={distance_mm:.4f} mm, F={feedrate_mm_min:.2f} mm/min")

            #Send commands sequentially to mainboard using gcode handler and check complete (True) between each step
            success = self.comms.send_command("set_extruder_relative")
            if success:
                success = self.comms.send_command("pump_move", E=f"{distance_mm:0.4f}",F=f"{feedrate_mm_min:.2f}")
            print(f"[{time.strftime('%H:%M:%S')}] Pump volume finished. Overall Success: {success}")
            return success
        

# if __name__ == "__main__":