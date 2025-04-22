# Main.py - Pump Test Script
import time
import sys
import configparser
import os

# --- Import Core Classes ---
# Assumes running from project root (NICHOLS BOT CONTROL)
try:
    # Adjust import path if your directory/file names are different
    from comms.gcode_handler import GCodeHandler, COMMANDS, BASE_HTTP_URL, WS_URL
    from hardware_modules.pump import Pump
    # from hardware_modules.robot import Robot
    from hardware_modules.sonicator import Sonicator
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
    config = configparser.ConfigParser(allow_no_value=True) # Allow empty values if needed
    # Default values in case config file is missing or incomplete
    pump_config_defaults = {
        'mm_per_ml': '1.0', # Use strings for defaults with getfloat
        'default_rate_ml_min': '5.0',
        'max_feedrate_mm_min': '400.0'
    }

    if not os.path.exists(CONFIG_FILE):
        print(f"Warning: Configuration file '{CONFIG_FILE}' not found.")
        print("Using default fallback values for Pump config.")
        # Convert defaults to float here
        return {k: float(v) for k, v in pump_config_defaults.items()}

    try:
        config.read(CONFIG_FILE)
        # Read pump section, providing fallbacks from defaults dictionary
        pump_config = {
            'mm_per_ml': config.getfloat('Pump', 'mm_per_ml',
                                         fallback=float(pump_config_defaults['mm_per_ml'])),
            'default_rate_ml_min': config.getfloat('Pump', 'default_rate_ml_min',
                                                  fallback=float(pump_config_defaults['default_rate_ml_min'])),
            'max_feedrate': config.getfloat('Pump', 'max_feedrate_mm_min',
                                             fallback=float(pump_config_defaults['max_feedrate_mm_min']))
        }
        # TODO: Add loading for other sections if needed (e.g., URLs if not imported)
        # http_url = config.get('Connection', 'http_url', fallback=BASE_HTTP_URL)
        # ws_url = config.get('Connection', 'ws_url', fallback=WS_URL)

        print("Configuration loaded from config.ini")
        return pump_config #, http_url, ws_url
    except Exception as e:
        print(f"Error reading configuration file '{CONFIG_FILE}': {e}")
        print("Using default fallback values for Pump config.")
        # Convert defaults to float here
        return {k: float(v) for k, v in pump_config_defaults.items()}

# --- Main Execution ---
if __name__ == "__main__":
    print("--- Pump Test Script ---")

    pump_config = load_config()
    # Assuming URLs and COMMANDS are imported from gcode_handler for now
    # If they were in config: handler = GCodeHandler(http_url, ws_url, COMMANDS)
    handler = GCodeHandler(BASE_HTTP_URL, WS_URL, COMMANDS)
    pump = Pump(
        comms=handler,
        mm_per_ml=pump_config['mm_per_ml'],
        default_rate_ml_min=pump_config['default_rate_ml_min'],
        
    )
    # Instantiate other devices if needed for combined tests
    # robot = Robot(handler, ...)
    # sonicator = Sonicator(handler, ...)

    try:
        print("\nAttempting to connect...")
        # Connect the handler (essential step)
        if handler.connect():
            print("\n--- Running Pump Tests ---")

            # --- Your Test Sequence ---
            # print("\n--- Test 1: Pump Volume (Default Rate) ---")
            # pump.pump_volume(volume_ml=10) # Pump 0.5mL at default rate
            # time.sleep(1) # Small pause between tests for observation

            print("\n--- Test 2: Pump Volume (Specific Rate) ---")
            pump.pump_volume(volume_ml=2, flowrate_ml_min=70.0) # Pump 1mL at 10 mL/min
            time.sleep(1)

            # print("\n--- Test 3: Pump Duration (Default Rate) ---")
            # pump.pump_duration(duration_s=10.0) # Pump for 10s at default rate
            # time.sleep(1)

            # print("\n--- Test 4: Pump Duration (Specific Negative Rate) ---")
            # pump.pump_duration(duration_s=5.0, flowrate_ml_min=-3.0) # Pump backwards for 5s at 3 mL/min
            # time.sleep(1)

            # print("\n--- Test 5: Pump Zero Volume ---")
            # pump.pump_volume(volume_ml=0) # Should do nothing or print warning

            # Add more tests as needed

            print("\n--- Pump Testing Finished ---")
        else:
            print("Failed to connect to the GCode Handler.")

    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected. Disconnecting...")
    except Exception as e:
         print(f"\nAn unexpected error occurred during testing: {e}")
         import traceback
         traceback.print_exc() # Print detailed traceback for debugging
    finally:
        # Ensure disconnection happens
        print("\nDisconnecting handler...")
        # Check if handler was successfully created before disconnecting
        if 'handler' in locals() and handler:
            handler.disconnect()
        print("Script finished.")

