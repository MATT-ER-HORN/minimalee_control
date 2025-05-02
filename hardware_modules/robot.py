import time
import math
import json 
import os
import sys
from comms.wifi_handler import WifiHandler
from comms.serial_handler import SerialHandler



class Robot:
    """
    High-level control class for the 3-axis Cartesian robot.
    Handles movement commands and applying initial configuration.
    Reads named locations directly from a JSON file.
    """

    
    def __init__(self, communicator, # No type hint here, but checked below
                 safe_z: float,
                 locations_filepath: str = 'locations.json', # Path to locations file
                 init_gcode_filepath: str | None = None,
                 default_speed: float | None = 3000.0):
        """
        Initializes the Robot controller.

        Args:
            communicator (WifiHandler | SerialHandler): The handler instance for sending commands.
            safe_z (float): A Z-height considered safe for XY travel without collision.
            locations_filepath (str): Path to the JSON file containing named locations.
            init_gcode_filepath (str | None): Optional path to a file containing
                                              G-code commands to send upon initialization.
            default_speed (float | None): Default travel speed (mm/min) if not specified.
        """

        self.comms = communicator
        self.safe_z = float(safe_z)
        self.default_speed = float(default_speed) if default_speed is not None else None
        self.current_pos = {'x': None, 'y': None, 'z': None} # Placeholder
        self.locations_filepath = locations_filepath
        self.locations = {} 
        self.init_gcode_filepath = init_gcode_filepath
        self.init_gcode_commands = []

        print(f"Robot initialized using {type(self.comms).__name__}: safe_z={self.safe_z}, default_speed={self.default_speed}")
        # Re-added call to load locations
        self._load_locations()
        self._load_init_gcode()

    # --- Internal Methods ---
    # Re-added _load_locations

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

    # Removed _save_locations

    def _load_init_gcode(self):
        """Loads G-code commands from the init file, skipping comments/empty lines."""
        self.init_gcode_commands = [];
        if self.init_gcode_filepath and os.path.exists(self.init_gcode_filepath):
            try:
                with open(self.init_gcode_filepath, 'r') as f:
                    for line in f:
                        cleaned_line = line.strip(); comment_index = cleaned_line.find(';');
                        if comment_index != -1: cleaned_line = cleaned_line[:comment_index].strip()
                        if cleaned_line: self.init_gcode_commands.append(cleaned_line)
                print(f"Loaded {len(self.init_gcode_commands)} init G-code commands from {self.init_gcode_filepath}")
            except Exception as e: print(f"Error loading init G-code file {self.init_gcode_filepath}: {e}")
        elif self.init_gcode_filepath: print(f"Warning: Init G-code file not found: {self.init_gcode_filepath}")

    def _get_speed(self, speed: float | None = None) -> float | None:
        """Returns the speed to use (provided or default), or None."""
        if speed is not None:
            if not isinstance(speed, (int, float)) or speed <= 0: print(f"Warning: Invalid speed specified ({speed}), using default."); return self.default_speed
            return float(speed)
        return self.default_speed

    # --- Public Methods ---
    # Removed add_location

    def apply_initial_config(self) -> bool:
        """Sends the loaded initial G-code commands to the controller."""
        if not self.init_gcode_commands: print("No initial G-code commands loaded."); return True
        print(f"\n[{time.strftime('%H:%M:%S')}] Applying {len(self.init_gcode_commands)} initial config commands...")
        all_sent_ok = True
        for i, command in enumerate(self.init_gcode_commands):
            print(f"  Sending init command {i+1}/{len(self.init_gcode_commands)}: {command}")
            if not self.comms.send_raw_gcode(command):
                print(f"  Error: Failed to send init command: {command}"); all_sent_ok = False; # break
            time.sleep(0.05)
        print(f"Finished applying initial configuration commands. Success: {all_sent_ok}"); return all_sent_ok

    def home(self, axes: str = 'xyz') -> bool:
        """Homes the specified axes."""
        print(f"\n[{time.strftime('%H:%M:%S')}] Homing axes: {axes}")
        if 'x' in axes.lower() or 'y' in axes.lower() or 'z' in axes.lower():
             success = self.comms.send_command("home_all")
             if success: self.current_pos = {'x': 0.0, 'y': 0.0, 'z': None}; print("Homing potentially complete.")
             return success
        else: print("No valid axes specified for homing."); return False

    def get_position(self) -> dict | None:
        """Gets the current XYZ position from the controller. (Requires handler implementation)"""
        print("Warning: get_position() is not fully implemented in Robot class (needs handler support).");
        return None

    def move_z(self, z: float, speed: float | None = None) -> bool:
        """Moves only the Z axis to the specified height."""
        target_speed = self._get_speed(speed); print(f"\n[{time.strftime('%H:%M:%S')}] Moving Z to {z:.3f} at speed {target_speed or 'default'}")
        success = self.comms.send_command("move", Z=z, F=target_speed);
        if success: self.current_pos['z'] = z;
        return success

    def move_xy(self, x: float, y: float, speed: float | None = None) -> bool:
        """Moves only the X and Y axes to the specified coordinates."""
        target_speed = self._get_speed(speed); print(f"\n[{time.strftime('%H:%M:%S')}] Moving XY to ({x:.3f}, {y:.3f}) at speed {target_speed or 'default'}")
        success = self.comms.send_command("move", X=x, Y=y, F=target_speed)
        if success: self.current_pos['x'] = x; self.current_pos['y'] = y;
        return success

    def move_to(self, x: float, y: float, z: float, speed: float | None = None) -> bool:
        """Moves safely to the target XYZ coordinates."""
        target_speed = self._get_speed(speed); print(f"\n[{time.strftime('%H:%M:%S')}] Moving safely to ({x:.3f}, {y:.3f}, {z:.3f}) at speed {target_speed or 'default'}")
        print("  Step 1: Moving to safe Z height..."); success = self.move_z(self.safe_z, target_speed)
        if not success: print("  Error: Failed to move to safe Z height."); return False
        print("  Step 2: Moving to target XY..."); success = self.move_xy(x, y, target_speed)
        if not success: print("  Error: Failed to move to target XY."); return False
        if not math.isclose(z, self.safe_z, abs_tol=1e-3):
            print("  Step 3: Moving to target Z height..."); success = self.move_z(z, target_speed)
            if not success: print("  Error: Failed to move to target Z height."); return False
        else:
            print("  Step 3: Already at target Z height (safe Z)."); success = True
        print(f"[{time.strftime('%H:%M:%S')}] Safe move finished. Overall Success: {success}"); return success

    # Re-added move_to_location
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
        # Get location directly from the internal dictionary loaded from JSON
        location_coords = self.locations.get(name)

        if location_coords is None:
            print(f"Error: Location '{name}' not found in loaded locations ({self.locations_filepath}).")
            return False
        # Basic validation of the loaded dictionary structure
        if not isinstance(location_coords, dict) or not all(key in location_coords for key in ('x', 'y', 'z')):
             print(f"Error: Location '{name}' in {self.locations_filepath} has invalid format: {location_coords}")
             return False

        try:
            target_x = float(location_coords['x'])
            target_y = float(location_coords['y'])
            target_z = float(location_coords['z']) + z_offset
        except (ValueError, TypeError) as e:
             print(f"Error: Invalid coordinate types for location '{name}': {e}")
             return False

        # Call the safe move method
        return self.move_to(target_x, target_y, target_z, speed)

    def set_absolute_positioning(self) -> bool:
        """Sets the controller to absolute positioning mode (G90)."""
        print(f"\n[{time.strftime('%H:%M:%S')}] Setting absolute positioning (G90)...");
        return self.comms.send_command("set_absolute")

    def set_relative_positioning(self) -> bool:
        """Sets the controller to relative positioning mode (G91)."""
        print(f"\n[{time.strftime('%H:%M:%S')}] Setting relative positioning (G91)...");
        return self.comms.send_command("set_relative")

