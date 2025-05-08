
import sys
import os
import configparser
import time
import traceback
import logging

# Get the absolute path of the directory containing this file (plugin/)
plugin_dir = os.path.dirname(os.path.abspath(__file__))
# Go up ONE level to get the project root
project_root = os.path.abspath(os.path.join(plugin_dir, '..'))
# Add the project root to the Python path if it's not already there
if project_root not in sys.path:
    print(f"Adding project root to sys.path: {project_root}")
    sys.path.insert(0, project_root)
# --- End path modification ---

# --- Now imports should work from the project root ---
from flask import Flask, render_template, request, jsonify
try:
    # Assuming these names and locations are correct relative to project root
    from comms.wifi_handler import WifiHandler # Use correct name if changed (e.g., ESP3DHandler)
    from comms.serial_handler import SerialHandler
    from comms.commands import COMMANDS
    from hardware_modules.robot import Robot
    from hardware_modules.pump import Pump
    from hardware_modules.sonicator import Sonicator
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(f"Could not import required modules from 'comms' or 'hardware_modules'. Check paths, __init__.py files, and ensure script is run correctly. Error: {e}")

# --- Configuration (Relative to project root now) ---
CONFIG_FILE = os.path.join(project_root, 'config.ini')
LOCATIONS_FILE = os.path.join(project_root, 'locations.json')
INIT_GCODE_FILE = os.path.join(project_root, 'robot_init.gcode')

# --- Global Variables ---
handler = None
robot = None
pump = None     # Uncomment if using
sonicator = None # Uncomment if using

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Flask App Setup ---
# Use template_folder='templates' relative to this app.py file
app = Flask(__name__, template_folder='templates', static_folder='static')

# --- Helper Functions ---
def initialize_system():
    """Loads config, creates handler and device instances, connects."""
    global handler, robot, pump, sonicator # Allow modification of global variables

    logging.info("--- Initializing Nichols Bot Control System ---")
    config = configparser.ConfigParser(inline_comment_prefixes=';')
    if not os.path.exists(CONFIG_FILE):
        logging.error(f"Configuration file '{CONFIG_FILE}' not found. Exiting.")
        sys.exit(1)
    config.read(CONFIG_FILE)

    try:
        comm_mode = config.get('Connection', 'mode', fallback='wifi').lower()
        robot_safe_z = config.getfloat('Robot', 'safe_z')
        robot_default_speed = config.getfloat('Robot', 'default_speed')
        # Load pump config
        pump_mm_per_ml = config.getfloat('Pump', 'mm_per_ml')
        # pump_default_rate = config.getfloat('Pump', 'default_rate_ml_min') # Removed in simplified Pump
        # pump_max_feedrate = config.getfloat('Pump', 'max_feedrate_mm_min') # Removed in simplified Pump

        logging.info(f"Selected communication mode: {comm_mode}")
        # Instantiate Handler (assuming COMMANDS imported correctly)
        if comm_mode == 'serial':
            serial_port = config.get('Connection', 'serial_port')
            baud_rate = config.getint('Connection', 'baud_rate')
            handler = SerialHandler(port=serial_port, baudrate=baud_rate, commands_dict=COMMANDS)
        elif comm_mode == 'wifi':
            # Load URLs from config or use defaults defined elsewhere (e.g., in handler file or imported)
            http_url = config.get('Connection', 'http_url', fallback='http://192.168.0.1:80') # Example fallback
            ws_url = config.get('Connection', 'ws_url', fallback='ws://192.168.0.1:81/')   # Example fallback
            handler = WifiHandler(http_url=http_url, ws_url=ws_url, commands_dict=COMMANDS)
        else:
            logging.error(f"Invalid communication mode '{comm_mode}' in config.ini.")
            sys.exit(1)

        # Instantiate Devices
        robot = Robot(
            communicator=handler,
            safe_z=robot_safe_z,
            default_speed=robot_default_speed,
            locations_filepath=LOCATIONS_FILE,
            init_gcode_filepath=INIT_GCODE_FILE
        )
        pump = Pump(
            comms=handler,
            mm_per_ml=pump_mm_per_ml
            # Pass other pump args if needed
        )
        sonicator = Sonicator(
            comms=handler
        )

        logging.info("Components instantiated. Connecting...")
        if not handler.connect():
            logging.error("Failed to connect to the GCode Handler.")
            sys.exit(1)

        logging.info("Applying initial robot configuration...")
        if not robot.apply_initial_config():
            logging.warning("Failed to apply initial robot configuration.")
            # Decide if this is fatal

        logging.info("--- System Initialized Successfully ---")
        return True

    except (configparser.Error, KeyError, ValueError) as e:
        logging.error(f"Error processing configuration file '{CONFIG_FILE}': {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error during initialization: {e}")
        traceback.print_exc()
        sys.exit(1)

# --- Flask Routes ---
# (Routes remain the same as before)
@app.route('/')
def index():
    """Render the main control page."""
    # Ensure robot exists before accessing locations
    locations = robot.locations if robot and hasattr(robot, 'locations') else {}
    return render_template('index.html', locations=locations)

@app.route('/move', methods=['POST'])
def handle_move():
    """Handle jogging movements."""
    if not robot or not handler or not handler.is_connected: return jsonify({"status": "error", "message": "Robot not initialized or connected"}), 500
    direction = request.form.get('direction'); step = float(request.form.get('step', 10.0)); speed = robot.default_speed
    logging.info(f"Received move request: direction={direction}, step={step}")
    success = False
    if direction == 'x_plus': success = robot.move_relative(dx=step, speed=speed)
    elif direction == 'x_minus': success = robot.move_relative(dx=-step, speed=speed)
    elif direction == 'y_plus': success = robot.move_relative(dy=step, speed=speed)
    elif direction == 'y_minus': success = robot.move_relative(dy=-step, speed=speed)
    elif direction == 'z_plus': success = robot.move_relative(dz=step, speed=speed)
    elif direction == 'z_minus': success = robot.move_relative(dz=-step, speed=speed)
    else: return jsonify({"status": "error", "message": "Invalid direction"}), 400
    if success: return jsonify({"status": "ok", "message": f"Move {direction} sent."})
    else: return jsonify({"status": "error", "message": f"Failed to send move {direction}."}), 500

@app.route('/get_position', methods=['GET'])
def get_current_position():
    """Get the current position (stubbed/optimistic)."""
    if not robot: return jsonify({"status": "error", "message": "Robot not initialized"}), 500
    # Use the potentially optimistic position stored in the robot object
    pos = robot.current_pos
    # Attempt to update with a fresh reading (best effort)
    live_pos = robot.get_position() # Call without update_internal
    if live_pos:
        pos = live_pos # Use live position if available
        robot.current_pos = live_pos # Update internal state

    if pos and pos.get('x') is not None: # Check if position is valid
        return jsonify({"status": "ok", "position": pos})
    else:
        # Return the potentially stale position if live failed, or indicate unknown
        unknown_pos = {'x': None, 'y': None, 'z': None, 'e': None}
        return jsonify({"status": "warning", "message": "Could not retrieve current position.", "position": pos or unknown_pos})


@app.route('/save_location', methods=['POST'])
def save_location():
    """Save the current position with a given name."""
    if not robot or not handler or not handler.is_connected: return jsonify({"status": "error", "message": "Robot not initialized or connected"}), 500
    name = request.form.get('name');
    if not name: return jsonify({"status": "error", "message": "Location name cannot be empty"}), 400
    logging.info(f"Request to save location: '{name}'")

    # --- IMPORTANT: Get REAL position before saving ---
    # *** FIX: Call get_position() without the argument ***
    current_pos = robot.get_position() # Try to update from M114
    if current_pos is None:
         # Fallback to the potentially stale internal value if M114 failed
         current_pos = robot.current_pos
         logging.warning(f"Could not get live position, saving potentially stale position: {current_pos}")
         if current_pos.get('x') is None: # Check if we have any valid coordinates
              return jsonify({"status": "error", "message": "Cannot determine current position to save."}), 500

    # Ensure we have valid coordinates before saving
    if not all(k in current_pos and current_pos[k] is not None for k in ('x', 'y', 'z')):
         return jsonify({"status": "error", "message": f"Cannot save, current position data is incomplete: {current_pos}"}), 500

    # Use the Robot class's method to add/update and save to JSON
    success = robot.add_location(name, current_pos['x'], current_pos['y'], current_pos['z'])

    if success:
        # Return the updated locations list for the frontend
        return jsonify({"status": "ok", "message": f"Location '{name}' saved.", "locations": robot.locations})
    else:
        return jsonify({"status": "error", "message": f"Failed to save location '{name}'."}), 500

@app.route('/home', methods=['POST'])
def handle_home():
    """Handle homing request."""
    if not robot or not handler or not handler.is_connected: return jsonify({"status": "error", "message": "Robot not initialized or connected"}), 500
    logging.info("Received home request")
    success = robot.home()
    if success: return jsonify({"status": "ok", "message": "Homing command sent."})
    else: return jsonify({"status": "error", "message": "Failed to send home command."}), 500


# # --- Teardown ---
# @app.teardown_appcontext
# def shutdown_handler(exception=None):
#     global handler
#     if handler and getattr(handler, 'is_connected', False):
#         logging.info("Flask app shutting down, disconnecting handler...")
#         handler.disconnect()

# --- Main Execution ---
if __name__ == '__main__':
    # Initialize system first
    if initialize_system():
        logging.info("Starting Flask development server...")
        # Run the app
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False) # Disable reloader for serial stability
    else:
        logging.error("System initialization failed. Flask app will not start.")

