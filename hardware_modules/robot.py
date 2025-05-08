import time
import math
import json
import os
import sys
import re
# Need Queue and Empty for get_position logic
from queue import Queue, Empty
# Import Handler Classes
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
        # Runtime check remains important
        if not isinstance(communicator, (WifiHandler, SerialHandler)):
             raise TypeError("Communicator must be an instance of WifiHandler or SerialHandler")
        # Other validation remains the same
        if not isinstance(safe_z, (int, float)):
             raise TypeError("safe_z must be a number")
        if default_speed is not None and (not isinstance(default_speed, (int, float)) or default_speed <= 0):
             raise ValueError("default_speed must be a positive number or None")
        if not isinstance(locations_filepath, str) or not locations_filepath:
             raise ValueError("locations_filepath must be a non-empty string.")
        if init_gcode_filepath is not None and not isinstance(init_gcode_filepath, str):
             raise ValueError("init_gcode_filepath must be a string or None.")


        self.comms = communicator
        self.safe_z = float(safe_z)
        self.default_speed = float(default_speed) if default_speed is not None else None
        self.current_pos = {'x': None, 'y': None, 'z': None, 'e': None}
        self.locations_filepath = locations_filepath
        self.locations = {}
        self.init_gcode_filepath = init_gcode_filepath
        self.init_gcode_commands = []
        self.m114_pattern = re.compile(r"X:([-\d\.]+) Y:([-\d\.]+) Z:([-\d\.]+) E:([-\d\.]+)")

        print(f"Robot initialized using {type(self.comms).__name__}: safe_z={self.safe_z}, default_speed={self.default_speed}")
        # Re-added call to load locations
        self._load_locations()
        self._load_init_gcode()

    # --- Internal Methods ---


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
            with open(temp_filepath, 'w') as f: json.dump(self.locations, f, indent=4)
            os.replace(temp_filepath, self.locations_filepath);
            print(f"Saved locations to {self.locations_filepath}") # Confirmation
            return True
        except Exception as e:
            print(f"Error saving locations to {self.locations_filepath}: {e}")
            # Attempt to remove temporary file if it exists
            if os.path.exists(temp_filepath):
                # --- FIX: Use standard indentation for inner try/except ---
                try:
                     os.remove(temp_filepath)
                except Exception as remove_e:
                     # Optionally log the remove error, but don't stop the outer exception handling
                     print(f"  Warning: Could not remove temp file {temp_filepath}: {remove_e}")
                # --- End FIX ---
            return False # This should now be parsed correctly

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
        """Homes the specified axes and attempts to update position."""
        print(f"\n[{time.strftime('%H:%M:%S')}] Homing axes: {axes}")
        if 'x' in axes.lower() or 'y' in axes.lower() or 'z' in axes.lower():
             success = self.comms.send_command("home_all") # Assumes this waits
             if success:
                 print("Homing command successful. Attempting to get position...")
                 # Try to get actual position to confirm home location
                 self.get_position(update_internal=True) # Call the updated get_position
                 print(f"Homing sequence finished. Current position: {self.current_pos}")
             return success
        else: print("No valid axes specified for homing."); return False

   
    def get_position(self, update_internal: bool = True) -> dict | None:
        """
        Sends M114, waits for completion, then parses the position report
        from the handler's message queue.

        Requires "get_position" command in commands.py to have "wait_after": True.

        Args:
            update_internal (bool): If True (default), updates self.current_pos.

        Returns:
            dict | None: Dictionary {'x': float, 'y': float, 'z': float, 'e': float}
                         or None if sending/parsing fails or timeout occurs.
        """
        print(f"[{time.strftime('%H:%M:%S')}] Requesting position (M114)...")

        # Check handler prerequisites
        if not hasattr(self.comms, 'message_queue') or not isinstance(self.comms.message_queue, Queue):
            print("Error: Communicator object missing valid 'message_queue'.")
            return None
        if not hasattr(self.comms, '_clear_queue'):
             print("Error: Communicator object missing '_clear_queue' method.")
             # Proceeding without clearing might read old data.

        # Clear queue BEFORE sending M114
        try: self.comms._clear_queue()
        except Exception as e: print(f"Error calling _clear_queue: {e}")

        # Send M114 command and wait for its 'ok'
        # CRITICAL: Assumes "get_position" has wait_after=True in COMMANDS
        if not self.comms.send_command("get_position"):
             print("Error: Failed to send M114 command or wait failed.")
             return None

        # Search queue for the position report AFTER 'ok' is received
        print("  M114 sent and 'ok' received. Searching queue for position report...")
        found_pos = None
        search_start_time = time.time()
        search_timeout = 2.0 # Time to look for the report after 'ok'

        # Consume messages until the report is found or timeout
        temp_message_store = [] # Store messages temporarily if needed
        while time.time() - search_start_time < search_timeout:
            try:
                # Use a short timeout on get() to avoid blocking the main thread for too long
                # if the message queue is temporarily empty but more data might arrive.
                message = self.comms.message_queue.get(timeout=0.1)
                temp_message_store.append(message) # Store for potential re-queuing
                # print(f"  [GetPos Check] Queue item: '{message}'") # Verbose Debug
                match = self.m114_pattern.search(message)
                if match:
                    try:
                        pos = {
                             'x': float(match.group(1)),
                             'y': float(match.group(2)),
                             'z': float(match.group(3)),
                             'e': float(match.group(4))
                        }
                        found_pos = pos
                        print(f"  Parsed position: {found_pos}")
                        if update_internal:
                             print("  Updating internal robot position.")
                             self.current_pos = found_pos
                        # Found it, stop searching
                        break
                    except (ValueError, IndexError) as parse_e:
                        print(f"  Error parsing numbers from M114 match: {match.groups()}. Error: {parse_e}")
                        # Continue searching other messages
            except Empty:
                # Queue is empty, continue loop until search_timeout
                if found_pos: break # Exit if found before queue became empty
                # No need to sleep here, the get(timeout=0.1) provides a small pause
                pass
            except Exception as e:
                print(f"  Error reading message queue during position search: {e}")
                break # Stop on unexpected errors

        # Optional: Put back messages that were read but not the position report?
        # This adds complexity. Simpler to assume other messages are less critical.
        # for msg in reversed(temp_message_store):
        #    if not self.m114_pattern.search(msg):
        #        try: self.comms.message_queue.put_nowait(msg)
        #        except Exception: pass # Ignore if queue full etc.

        if found_pos:
             return found_pos
        else:
             print("Warning: Did not find position report in queue within timeout after M114 'ok'.")
             # Return the last known position? Or None? None is safer.
             return None


    def move_z(self, z: float, speed: float | None = None) -> bool:
        """Moves only the Z axis to the specified height."""
        target_speed = self._get_speed(speed); print(f"\n[{time.strftime('%H:%M:%S')}] Moving Z to {z:.3f} at speed {target_speed or 'default'}")
        success = self.comms.send_command("move", Z=z, F=target_speed);
        if success: self.current_pos['z'] = z; # Optimistic update
        return success

    def move_xy(self, x: float, y: float, speed: float | None = None) -> bool:
        """Moves only the X and Y axes to the specified coordinates."""
        target_speed = self._get_speed(speed); print(f"\n[{time.strftime('%H:%M:%S')}] Moving XY to ({x:.3f}, {y:.3f}) at speed {target_speed or 'default'}")
        success = self.comms.send_command("move", X=x, Y=y, F=target_speed)
        if success: self.current_pos['x'] = x; self.current_pos['y'] = y; # Optimistic update
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


    def move_relative(self, dx: float = 0, dy: float = 0, dz: float = 0, speed: float | None = None) -> bool:
        """
        Moves the robot by a relative amount in X, Y, or Z.
        """
        target_speed = self._get_speed(speed) # Use helper to get default speed if needed
        print(f"\n[{time.strftime('%H:%M:%S')}] Moving relatively by (dX:{dx:.3f}, dY:{dy:.3f}, dZ:{dz:.3f}) at speed {target_speed or 'default'}")

        # Build G-code command string parts
        gcode_parts = ["G91"] # Set relative mode first
        move_cmd = "G1"
        has_move = False # Track if any axis is actually moving
        if dx != 0: move_cmd += f" X{dx:.3f}"; has_move = True
        if dy != 0: move_cmd += f" Y{dy:.3f}"; has_move = True
        if dz != 0: move_cmd += f" Z{dz:.3f}"; has_move = True

        # Only add the move command if there's movement, and add speed if specified
        if has_move:
            if target_speed is not None: move_cmd += f" F{target_speed:.1f}"
            gcode_parts.append(move_cmd)

        gcode_parts.append("G90") # Always set back to absolute mode

        success = True
        for cmd in gcode_parts:
             if not self.comms.send_raw_gcode(cmd):
                  success = False; print(f"  Error sending raw command: {cmd}"); break
             time.sleep(0.05) # Small delay between raw commands

        if success:
             print("Relative move commands sent.")
             # Update optimistic position if possible
             if has_move and self.current_pos['x'] is not None:
                 self.current_pos['x'] += dx
                 self.current_pos['y'] += dy
                 self.current_pos['z'] += dz
        else:
             print("Error sending relative move sequence.")
             self.comms.send_raw_gcode("G90") # Ensure back to absolute

        return success

    def move_to_location(self, name: str, z_offset: float = 0.0, speed: float | None = None) -> bool:
        """
        Retrieves coordinates for a named location from the loaded dictionary and moves safely to it.
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

    def add_location(self, name: str, x: float, y: float, z: float) -> bool:
         """Adds or updates a named location and saves to the JSON file."""
         if not isinstance(name, str) or not name: print("Error: Location name must be non-empty string."); return False
         try:
            coords = {'x': float(x), 'y': float(y), 'z': float(z)}; self.locations[name] = coords; print(f"Added/Updated location '{name}' in memory: {coords}")
            if self._save_locations(): return True
            else: print(f"Error: Failed to save locations file after updating '{name}'."); return False
         except (ValueError, TypeError) as e: print(f"Error adding location '{name}': Invalid coordinates ({x}, {y}, {z}). {e}"); return False

    def set_absolute_positioning(self) -> bool:
        """Sets the controller to absolute positioning mode (G90)."""
        print(f"\n[{time.strftime('%H:%M:%S')}] Setting absolute positioning (G90)...");
        return self.comms.send_command("set_absolute")

    def set_relative_positioning(self) -> bool:
        """Sets the controller to relative positioning mode (G91)."""
        print(f"\n[{time.strftime('%H:%M:%S')}] Setting relative positioning (G91)...");
        return self.comms.send_command("set_relative")

