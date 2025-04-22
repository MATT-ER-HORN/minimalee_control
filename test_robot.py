import time
import sys
import configparser
import os

# --- Import Core Classes ---
try:
    # Adjust path based on actual structure if it differs
    from comms.gcode_handler import GCodeHandler, COMMANDS, BASE_HTTP_URL, WS_URL
    from hardware_modules.robot import Robot
    # LocationManager is no longer needed here
    # from hardware_modules.pump import Pump # Import if needed
    # from hardware_modules.sonicator import Sonicator # Import if needed
except ImportError as e:
    print(f"Import Error: {e}")
    print("Ensure you are running this script from the project root directory")
    print("and that __init__.py files exist in 'comms' and 'hardware_modules'.")
    print("Also check that necessary classes/variables are defined in imported modules.")
    sys.exit(1)

# --- Configuration Loading ---
CONFIG_FILE = 'config.ini' # Assumes config.ini is in the project root

def load_config():
    """Loads configuration from config.ini"""
    config = configparser.ConfigParser(allow_no_value=True)
    # Default values
    robot_config_defaults = {
        'safe_z': '100.0',
        'default_speed': '3000.0'
    }
    # Add other sections/defaults if needed (e.g., Pump, Connection)

    if not os.path.exists(CONFIG_FILE):
        print(f"Warning: Configuration file '{CONFIG_FILE}' not found.")
        print("Using default fallback values for Robot config.")
        return {k: float(v) for k, v in robot_config_defaults.items()}

    try:
        config.read(CONFIG_FILE)
        robot_config = {
            'safe_z': config.getfloat('Robot', 'safe_z',
                                       fallback=float(robot_config_defaults['safe_z'])),
            'default_speed': config.getfloat('Robot', 'default_speed',
                                             fallback=float(robot_config_defaults['default_speed']))
        }
        # TODO: Load Connection URLs, Pump/Sonicator config if needed

        print("Configuration loaded from config.ini")
        return robot_config # Only returning robot config for this example
    except Exception as e:
        print(f"Error reading configuration file '{CONFIG_FILE}': {e}")
        print("Using default fallback values for Robot config.")
        return {k: float(v) for k, v in robot_config_defaults.items()}

# --- Test Function Definition ---
def test_location_sequence(robot_instance: Robot):
    """
    Homes the robot and then attempts to move to each location
    loaded from the locations JSON file.

    Args:
        robot_instance (Robot): An initialized and connected Robot object.
    """
    print("\n--- Starting Location Sequence Test ---")

    # 1. Home the robot first
    print("Attempting to home all axes...")
    if not robot_instance.home():
        print("Error: Homing failed. Aborting sequence test.")
        return False # Indicate failure
    print("Homing complete. Proceeding to locations...")
    time.sleep(2) # Pause after homing

    # 2. Get location names from the robot instance (which loaded them from JSON)
    # Sort keys for a consistent order during testing
    location_names = sorted(robot_instance.locations.keys())
    if not location_names:
        print("No locations loaded from JSON file. Cannot run sequence.")
        return False # Indicate failure (no locations to test)

    print(f"Found locations: {', '.join(location_names)}")

    # 3. Iterate and move to each location
    all_moves_succeeded = True
    for name in location_names:
        print(f"\nMoving to location: '{name}'...")
        # Using move_to_location which incorporates the safe Z logic
        success = robot_instance.move_to_location(name)
        if not success:
            print(f"Error: Failed to move to location '{name}'. Continuing sequence...")
            all_moves_succeeded = False
        else:
            print(f"Successfully moved to '{name}'.")
        time.sleep(2) # Pause at each location for observation

    print("\n--- Location Sequence Test Finished ---")
    if not all_moves_succeeded:
        print("Warning: One or more moves failed during the sequence.")
    return all_moves_succeeded


# --- Main Execution ---
if __name__ == "__main__":
    print("--- Robot Location Sequence Test Script ---")

    robot_config = load_config()
    # Assuming URLs and COMMANDS are imported from gcode_handler
    handler = GCodeHandler(BASE_HTTP_URL, WS_URL, COMMANDS)
    # Instantiate Robot (LocationManager removed, pass filepath instead)
    # Ensure 'locations.json' exists in the root or provide the correct path
    robot = Robot(
        communicator=handler,
        safe_z=robot_config['safe_z'],
        default_speed=robot_config['default_speed'],
        locations_filepath='locations.json' # Make sure this file exists!
    )
    # Instantiate other devices if needed
    # pump = Pump(...)
    # sonicator = Sonicator(...)

    try:
        print("\nAttempting to connect...")
        if handler.connect():
            print("\n--- Running Location Sequence Test ---")
            # Call the test function
            test_success = test_location_sequence(robot)
            print(f"\nOverall test sequence success: {test_success}")

            # You could add other tests here
            # e.g., robot.move_to(1, 2, 3)

        else:
            print("Failed to connect to the GCode Handler.")

    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected. Disconnecting...")
    except Exception as e:
         print(f"\nAn unexpected error occurred during testing: {e}")
         import traceback
         traceback.print_exc()
    finally:
        print("\nDisconnecting handler...")
        if 'handler' in locals() and handler:
            handler.disconnect()
        print("Script finished.")