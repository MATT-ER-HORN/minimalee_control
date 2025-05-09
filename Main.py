import configparser
import sys
import os
import traceback # Keep for debugging unexpected errors
import time # Keep for potential delays

# --- Import Core Classes ---

COMMANDS = None 
try:
    # Import handlers and the shared COMMANDS dictionary
    from comms.wifi_handler import WifiHandler, BASE_HTTP_URL, WS_URL # Keep URL imports if needed globally
    from comms.serial_handler import SerialHandler
    from comms.commands import COMMANDS # Import COMMANDS from its own file
    from hardware_modules.robot import Robot
    from hardware_modules.pump import Pump
    from hardware_modules.sonicator import Sonicator
    import ivoryos
    
    

    # --- DEBUG PRINT ---
    # Check if COMMANDS was successfully imported and is a dictionary
    if isinstance(COMMANDS, dict):
        print(f"DEBUG: Successfully imported COMMANDS dictionary with {len(COMMANDS)} entries.")
    else:
        print("DEBUG: COMMANDS was imported but is not a dictionary (or still None). Type:", type(COMMANDS))
        # Optionally exit if COMMANDS is critical and failed import here
        # sys.exit(1)
    # --- END DEBUG PRINT ---

except ImportError as e:
    print(f"Import Error: {e}")
    print("Ensure you are running this script from the project root directory")
    print("and that __init__.py files exist in 'comms' and 'hardware_modules'.")
    print("Also check that necessary classes/variables (like COMMANDS in comms/commands.py) exist.")
    sys.exit(1)
except Exception as e: # Catch other potential errors during import phase
    print(f"Unexpected error during imports: {e}")
    traceback.print_exc()
    sys.exit(1)

# --- Configuration Files ---
CONFIG_FILE = 'config.ini'
LOCATIONS_FILE = 'locations.json'
INIT_GCODE_FILE = 'robot_init.gcode' # Assuming Robot class still uses this

# --- Main Execution ---
if __name__ == "__main__":
    print("--- Initializing Nichols Bot Control System ---")

    # --- Check if COMMANDS is valid before proceeding ---
    if COMMANDS is None or not isinstance(COMMANDS, dict):
         print("Error: COMMANDS dictionary was not loaded correctly during import phase. Exiting.")
         sys.exit(1)
    # --- End Check ---

    handler = None # Define handler outside try block for finally clause

    try:
        # --- Load Config ---
        print(f"Loading configuration from {CONFIG_FILE}...")
        config = configparser.ConfigParser(inline_comment_prefixes=';')
        if not os.path.exists(CONFIG_FILE):
            print(f"Error: Configuration file '{CONFIG_FILE}' not found. Exiting.")
            sys.exit(1)
        config.read(CONFIG_FILE)

        # Determine communication mode
        comm_mode = config.get('Connection', 'mode', fallback='wifi').lower()

        # Load common robot/pump config (using .getfloat for robustness)
        robot_safe_z = config.getfloat('Robot', 'safe_z', fallback=100.0)
        robot_default_speed = config.getfloat('Robot', 'default_speed', fallback=3000.0)
        pump_mm_per_ml = config.getfloat('Pump', 'mm_per_ml', fallback=1.0)
        # Removed pump config not needed by simplified Pump class
        # pump_default_rate = config.getfloat('Pump', 'default_rate_ml_min', fallback=5.0)
        # pump_max_feedrate = config.getfloat('Pump', 'max_feedrate_mm_min', fallback=400.0)


        # --- Instantiate Handler based on Mode ---
        print(f"Selected communication mode: {comm_mode}")
        if comm_mode == 'serial':
            serial_port = config.get('Connection', 'serial_port')
            baud_rate = config.getint('Connection', 'baud_rate')
            # Removed serial_wait_timeout loading as it's defined inside SerialHandler
            # serial_wait_timeout = config.getfloat('Connection', 'serial_wait_timeout', fallback=120.0)
            print(f"Instantiating SerialHandler (Port: {serial_port}, Baud: {baud_rate})...")
            # Pass the imported COMMANDS dictionary
            # *** FIX: Removed wait_timeout argument ***
            handler = SerialHandler(
                port=serial_port,
                baudrate=baud_rate,
                commands_dict=COMMANDS
                # wait_timeout=serial_wait_timeout # Removed this line
            )
        elif comm_mode == 'wifi':
            # Assuming URLs are imported or defined globally for simplicity here
            print(f"Instantiating WifiHandler (HTTP: {BASE_HTTP_URL}, WS: {WS_URL})...")
            # Pass the imported COMMANDS dictionary
            handler = WifiHandler(
                http_url=BASE_HTTP_URL, # Pass explicitly if needed
                ws_url=WS_URL,         # Pass explicitly if needed
                commands_dict=COMMANDS # Pass COMMANDS here
            )
        else:
            print(f"Error: Invalid communication mode '{comm_mode}' in config.ini. Use 'wifi' or 'serial'.")
            sys.exit(1)

        # --- Instantiate Devices ---
        print("Instantiating devices...")
        robot = Robot(
            communicator=handler, # Pass the selected handler
            safe_z=robot_safe_z,
            default_speed=robot_default_speed,
            locations_filepath=LOCATIONS_FILE,
            # Assuming Robot still takes init_gcode_filepath based on previous versions
            init_gcode_filepath=INIT_GCODE_FILE
        )

        pump = Pump(
            comms=handler, # Pass the selected handler
            mm_per_ml=pump_mm_per_ml
            # Removed arguments not needed by simplified Pump class
            # default_rate_ml_min=pump_default_rate,
            # max_feedrate_mm_min=pump_max_feedrate
        )

        sonicator = Sonicator(
            comms=handler # Pass the selected handler
        )
        print("Components instantiated.")

        # --- Connect and Apply Initial Config ---
        print("\nAttempting to connect and apply config...")
        if not handler.connect():
            print("Error: Failed to connect to the GCode Handler.")
            sys.exit(1)

        # Apply initial config using the Robot instance
        # Assuming Robot class still has apply_initial_config method
        if not robot.apply_initial_config():
            print("Error: Failed to apply initial robot configuration.")
            if handler: handler.disconnect() # Try to disconnect if config failed
            sys.exit(1)

        # --- Ready for GUI ---
        print("--- System Initialized Successfully ---")
        print(f"Using {comm_mode.upper()} communication.")
        print("Handler, Robot, Pump, and Sonicator objects are ready.")

        # --- Run the GUI Tool with plugin ---
        # from ivoryos_plugin.plugin import plugin
        # print("\nStarting IvoryOS GUI...")
        # ivoryos.run(__name__, blueprint_plugins=plugin)

        # --- Run the GUI Tool with no plugin ---
        print("\nStarting IvoryOS GUI...")
        ivoryos.run(__name__)

    except configparser.Error as e:
         print(f"\nError reading configuration file '{CONFIG_FILE}': {e}")
         sys.exit(1)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected. Disconnecting...")
    except Exception as e:
         print(f"\nAn unexpected error occurred during initialization or runtime: {e}")
         traceback.print_exc()
    finally:
        # Ensure disconnection happens if handler was created and connected
        # Check if handler exists and has an 'is_connected' attribute before checking state
        if 'handler' in locals() and handler and getattr(handler, 'is_connected', False):
            print("\nDisconnecting handler...")
            handler.disconnect()
        print("Main script finished.")
