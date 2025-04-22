import time
import math
import json # Needed for loading/saving locations
import os   # Needed for file operations
from comms.gcode_handler import GCodeHandler
    

class Robot:
    """
    High-level control class for the 3-axis Cartesian robot.
    Reads named locations directly from a JSON file.
    """

    def __init__(self, communicator: GCodeHandler,
                 safe_z: float,
                 locations_filepath: str = 'locations.json', # Path to locations file
                 default_speed: float | None = 3000.0):
        """
        Initializes the Robot controller.

        Args:
            communicator (GCodeHandler): The GCodeHandler instance for sending commands.
            safe_z (float): A Z-height considered safe for XY travel without collision.
            locations_filepath (str): Path to the JSON file containing named locations.
            default_speed (float | None): Default travel speed (mm/min) if not specified.
                                          Set to None to use firmware default.
        """
        if not isinstance(communicator, GCodeHandler):
             raise TypeError("Communicator must be an instance of GCodeHandler")
        if not isinstance(safe_z, (int, float)):
             raise TypeError("safe_z must be a number")
        if default_speed is not None and (not isinstance(default_speed, (int, float)) or default_speed <= 0):
             raise ValueError("default_speed must be a positive number or None")
        if not isinstance(locations_filepath, str) or not locations_filepath:
             raise ValueError("locations_filepath must be a non-empty string.")

        self.comms = communicator
        self.safe_z = float(safe_z)
        self.default_speed = float(default_speed) if default_speed is not None else None
        self.current_pos = {'x': None, 'y': None, 'z': None} # Placeholder
        self.locations_filepath = locations_filepath
        self.locations = {} # Dictionary to hold loaded locations

        print(f"Robot initialized: safe_z={self.safe_z}, default_speed={self.default_speed}")
        self._load_locations() # Load locations on initialization

    def _load_locations(self):
        """Loads locations from the JSON file specified in self.locations_filepath."""
        if os.path.exists(self.locations_filepath):
            try:
                with open(self.locations_filepath, 'r') as f:
                    self.locations = json.load(f)
                print(f"Loaded {len(self.locations)} locations from {self.locations_filepath}")
            except json.JSONDecodeError:
                print(f"Error: Could not decode JSON from {self.locations_filepath}. No locations loaded.")
                self.locations = {}
            except Exception as e:
                print(f"Error loading locations file {self.locations_filepath}: {e}")
                self.locations = {}
        else:
            print(f"Location file {self.locations_filepath} not found. No locations loaded.")
            self.locations = {}

    def _save_locations(self) -> bool:
        """Saves the current locations dictionary back to the JSON file."""
        temp_filepath = self.locations_filepath + ".tmp"
        try:
            with open(temp_filepath, 'w') as f:
                json.dump(self.locations, f, indent=4)
            os.replace(temp_filepath, self.locations_filepath)
            # print(f"Saved {len(self.locations)} locations to {self.locations_filepath}")
            return True
        except Exception as e:
            print(f"Error saving locations to {self.locations_filepath}: {e}")
            if os.path.exists(temp_filepath):
                try: os.remove(temp_filepath)
                except Exception: pass
            return False

    def _get_speed(self, speed: float | None = None) -> float | None:
        """Returns the speed to use (provided or default), or None."""
        if speed is not None:
            if not isinstance(speed, (int, float)) or speed <= 0:
                 print(f"Warning: Invalid speed specified ({speed}), using default.")
                 return self.default_speed
            return float(speed)
        return self.default_speed # Can be None if default is None

    def home(self, axes: str = 'xyz') -> bool:
        """Homes the specified axes."""
        print(f"\n[{time.strftime('%H:%M:%S')}] Homing axes: {axes}")
        if 'x' in axes.lower() or 'y' in axes.lower() or 'z' in axes.lower():
             success = self.comms.send_command("home_all")
             if success:
                 self.current_pos = {'x': 0.0, 'y': 0.0, 'z': None} # Tentative position
                 print("Homing potentially complete (position might need verification).")
             return success
        else:
            print("No valid axes specified for homing.")
            return False

    def get_position(self) -> dict | None:
        """
        Gets the current XYZ position from the controller.
        NOTE: Requires implementation - parsing M114 response via WebSocket.
        """
        print("Warning: get_position() is not fully implemented.")
        return None # Return None until implemented

    def move_z(self, z: float, speed: float | None = None) -> bool:
        """Moves only the Z axis to the specified height."""
        target_speed = self._get_speed(speed)
        print(f"\n[{time.strftime('%H:%M:%S')}] Moving Z to {z:.3f} at speed {target_speed or 'default'}")
        success = self.comms.send_command("move", Z=z, F=target_speed)
        if success: self.current_pos['z'] = z # Optimistic update
        return success

    def move_xy(self, x: float, y: float, speed: float | None = None) -> bool:
        """Moves only the X and Y axes to the specified coordinates."""
        target_speed = self._get_speed(speed)
        print(f"\n[{time.strftime('%H:%M:%S')}] Moving XY to ({x:.3f}, {y:.3f}) at speed {target_speed or 'default'}")
        success = self.comms.send_command("move", X=x, Y=y, F=target_speed)
        if success: self.current_pos['x'] = x; self.current_pos['y'] = y # Optimistic update
        return success

    def move_to(self, x: float, y: float, z: float, speed: float | None = None) -> bool:
        """
        Moves safely to the target XYZ coordinates.
        1. Moves Z to safe height.
        2. Moves XY to target.
        3. Moves Z to target height.
        """
        target_speed = self._get_speed(speed)
        print(f"\n[{time.strftime('%H:%M:%S')}] Moving safely to ({x:.3f}, {y:.3f}, {z:.3f}) at speed {target_speed or 'default'}")

        print("  Step 1: Moving to safe Z height...")
        success = self.move_z(self.safe_z, target_speed)
        if not success: print("  Error: Failed to move to safe Z height."); return False

        print("  Step 2: Moving to target XY...")
        success = self.move_xy(x, y, target_speed)
        if not success: print("  Error: Failed to move to target XY."); return False

        if not math.isclose(z, self.safe_z, abs_tol=1e-3):
             print("  Step 3: Moving to target Z height...")
             success = self.move_z(z, target_speed)
             if not success: print("  Error: Failed to move to target Z height."); return False
        else:
             print("  Step 3: Already at target Z height (safe Z).")

        print(f"[{time.strftime('%H:%M:%S')}] Safe move finished. Overall Success: {success}")
        return success

    def move_to_location(self, name: str, z_offset: float = 0.0, speed: float | None = None) -> bool:
        """
        Retrieves coordinates for a named location from the loaded dictionary and moves safely to it.

        Args:
            name (str): The name of the location (key in the locations dictionary).
            z_offset (float): An optional offset to apply to the stored Z coordinate.
            speed (float | None): The travel speed (mm/min). Uses default if None.

        Returns:
            bool: True if move was successful, False otherwise.
        """
        print(f"\n[{time.strftime('%H:%M:%S')}] Moving to location '{name}' (Z offset: {z_offset:.3f})...")
        # Get location directly from the internal dictionary
        location_coords = self.locations.get(name)

        if location_coords is None:
            print(f"Error: Location '{name}' not found in loaded locations.")
            return False
        if not all(key in location_coords for key in ('x', 'y', 'z')):
             print(f"Error: Location '{name}' has invalid format: {location_coords}")
             return False

        try:
            target_x = float(location_coords['x'])
            target_y = float(location_coords['y'])
            target_z = float(location_coords['z']) + z_offset
        except (ValueError, TypeError) as e:
             print(f"Error: Invalid coordinate types for location '{name}': {e}")
             return False

        return self.move_to(target_x, target_y, target_z, speed)

    def add_location(self, name: str, x: float, y: float, z: float) -> bool:
         """
         Adds or updates a named location in the internal dictionary and saves to the JSON file.
         Useful for calibration or setup routines.
         """
         if not isinstance(name, str) or not name:
            print("Error: Location name must be a non-empty string.")
            return False
         try:
            coords = {'x': float(x), 'y': float(y), 'z': float(z)}
            self.locations[name] = coords # Update in-memory dictionary
            print(f"Added/Updated location '{name}' in memory: {coords}")
            # Save the entire dictionary back to the file
            if self._save_locations():
                 print(f"Successfully saved locations to {self.locations_filepath}")
                 return True
            else:
                 print(f"Error: Failed to save locations file after updating '{name}'.")
                 # Optionally remove the change from memory if save failed?
                 # del self.locations[name] # Or reload from file?
                 return False
         except (ValueError, TypeError) as e:
             print(f"Error adding location '{name}': Invalid coordinates ({x}, {y}, {z}). {e}")
             return False

    def set_absolute_positioning(self) -> bool:
         """Sets the controller to absolute positioning mode (G90)."""
         print(f"\n[{time.strftime('%H:%M:%S')}] Setting absolute positioning (G90)...")
         return self.comms.send_command("set_absolute")

    def set_relative_positioning(self) -> bool:
         """Sets the controller to relative positioning mode (G91)."""
         print(f"\n[{time.strftime('%H:%M:%S')}] Setting relative positioning (G91)...")
         return self.comms.send_command("set_relative")



