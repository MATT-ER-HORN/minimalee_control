import os
import logging # Import logging
from flask import Blueprint, render_template, request, jsonify, current_app, url_for # Import url_for

# --- Configure logging ---
# Basic configuration, adjust format and level as needed
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__) # Create a logger instance for this module

# --- Attempt to import GlobalConfig, provide fallback ---
try:
    from ivoryos.utils.global_config import GlobalConfig
    global_config = GlobalConfig()
    log.info("Successfully imported GlobalConfig from ivoryos.")
except ImportError:
    log.warning("Could not import GlobalConfig from ivoryos. Using fallback.")
    # Define fallback classes if GlobalConfig is not available
    class DummyHardware:
        # Add attributes expected by the routes to avoid AttributeError later
        locations = {}
        default_speed = 3000.0
        current_pos = {'x': None, 'y': None, 'z': None}
        is_connected = False # Assume not connected in fallback

        # Add dummy methods returning False or None as appropriate
        def move_relative(self, *args, **kwargs): return False
        def get_position(self, *args, **kwargs): return self.current_pos
        def add_location(self, *args, **kwargs): return False
        def home(self, *args, **kwargs): return False

    class DummyDeck:
        handler = DummyHardware() # Use DummyHardware for handler too
        robot = DummyHardware()
        pump = DummyHardware() # Add placeholders even if not used in these routes
        sonicator = DummyHardware() # Add placeholders

    class GlobalFallback:
        deck = DummyDeck()

    global_config = GlobalFallback() # Assign the fallback instance

# --- Define the Blueprint ---
plugin = Blueprint(
    "plugin",
    __name__,
    # Define paths relative to the current file's directory
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "static")
    # IvoryOS likely handles the url_prefix when registering the blueprint
)

# --- Main Route to Render UI ---
@plugin.route('/', endpoint='main')
def main():
    """Renders the main control interface."""
    log.info(f"Rendering main plugin page for endpoint '{request.endpoint}'.")
    # Check if the base template exists (depends on IvoryOS environment)
    base_exists = "base.html" in current_app.jinja_env.list_templates()

    # Safely get robot and locations from global_config
    robot = getattr(global_config.deck, 'robot', None)
    locations = getattr(robot, 'locations', {}) if robot else {}
    log.debug(f"Base template exists: {base_exists}, Robot found: {bool(robot)}, Locations: {locations}")

    # Generate API URLs dynamically using url_for relative to this blueprint
    # This ensures URLs are correct even with IvoryOS's prefixing
    try:
        api_urls = {
            "move": url_for('.handle_move'),
            "home": url_for('.handle_home'),
            "get_position": url_for('.get_current_position'),
            "save_location": url_for('.save_location')
        }
        log.debug(f"Generated API URLs: {api_urls}")
    except Exception as e:
        # This might happen if routes are not yet fully registered or context is wrong
        log.exception("Error generating API URLs with url_for!")
        api_urls = {} # Provide empty dict as fallback

    return render_template(
        'index.html',
        base_exists=base_exists,
        locations=locations,
        api_urls=api_urls
    )

# --- API Route for Moving the Robot ---
@plugin.route('/move', methods=['POST'], endpoint='handle_move')
def handle_move():
    """Handles relative movement commands for the robot."""
    log.info(f"Received request for endpoint '{request.endpoint}' ({request.method} {request.path})")
    robot = getattr(global_config.deck, 'robot', None)
    handler = getattr(global_config.deck, 'handler', None)
    # Check handler connectivity safely using getattr
    is_connected = getattr(handler, 'is_connected', False) if handler else False
    log.info(f"State check - Robot: {bool(robot)}, Handler: {bool(handler)}, Connected: {is_connected}")

    # Validate hardware state
    if not (robot and handler and is_connected):
        log.error("Move failed: Robot or Handler not ready or not connected.")
        return jsonify({"status": "error", "message": "Robot not ready or not connected"}), 500

    # Get parameters from the form data
    direction = request.form.get('direction')
    try:
        step = float(request.form.get('step', '10.0')) # Default to string '10.0'
        log.debug(f"Move parameters - Direction: {direction}, Step: {step}")
    except ValueError:
        log.warning(f"Invalid step value received: {request.form.get('step')}")
        return jsonify({"status": "error", "message": "Invalid step value"}), 400 # Bad Request

    # Map direction to coordinate changes
    dx = dy = dz = 0
    if direction == 'x_plus': dx = step
    elif direction == 'x_minus': dx = -step
    elif direction == 'y_plus': dy = step
    elif direction == 'y_minus': dy = -step
    elif direction == 'z_plus': dz = step
    elif direction == 'z_minus': dz = -step
    else:
        log.warning(f"Invalid direction received: {direction}")
        return jsonify({"status": "error", "message": "Invalid direction command"}), 400 # Bad Request

    # Execute the move command
    try:
        default_speed = getattr(robot, 'default_speed', 3000.0)
        log.info(f"Executing move_relative: dx={dx}, dy={dy}, dz={dz}, speed={default_speed}")
        success = robot.move_relative(dx=dx, dy=dy, dz=dz, speed=default_speed)
        if success:
            log.info(f"Move '{direction}' successful.")
            # Optionally update internal position after move if needed
            # robot.get_position(update_internal=True)
            return jsonify({"status": "ok", "message": f"Moved {direction} by {step}mm"})
        else:
            log.error("Robot move_relative command returned False.")
            return jsonify({"status": "error", "message": "Robot move command failed"}), 500 # Internal Server Error
    except Exception as e:
        log.exception("Exception during robot.move_relative!")
        return jsonify({"status": "error", "message": f"Error during move: {e}"}), 500

# --- API Route to Get Current Position ---
@plugin.route('/get_position', methods=['GET'], endpoint='get_current_position')
def get_position():
    """Retrieves the current position of the robot."""
    log.info(f"Received request for endpoint '{request.endpoint}' ({request.method} {request.path})")
    robot = getattr(global_config.deck, 'robot', None)
    handler = getattr(global_config.deck, 'handler', None)
    is_connected = getattr(handler, 'is_connected', False) if handler else False
    log.info(f"State check - Robot: {bool(robot)}, Handler: {bool(handler)}, Connected: {is_connected}")

    # No need to check connection strictly for get_position, but robot must exist
    if not robot:
        log.error("Get position failed: Robot object not found.")
        return jsonify({"status": "error", "message": "Robot not available"}), 500

    try:
        log.debug("Attempting to get robot position.")
        # Prefer fetching fresh position, fallback to stored current_pos
        pos = robot.get_position(update_internal=True) # Try to update from hardware
        if pos is None or pos.get('x') is None: # Check if fetch failed or incomplete
             log.warning("get_position() returned None or incomplete data, using stored current_pos.")
             pos = getattr(robot, 'current_pos', {'x': None, 'y': None, 'z': None})

        log.info(f"Returning position: {pos}")
        # Check if the position dictionary has valid coordinates
        if pos and pos.get('x') is not None and pos.get('y') is not None and pos.get('z') is not None:
            return jsonify({"status": "ok", "position": pos})
        else:
            log.warning("Position data is incomplete or unavailable.")
            return jsonify({"status": "warning", "message": "Position data unavailable", "position": pos or {}})

    except Exception as e:
        log.exception("Exception during robot.get_position!")
        return jsonify({"status": "error", "message": f"Error getting position: {e}"}), 500

# --- API Route to Save Current Location ---
@plugin.route('/save_location', methods=['POST'], endpoint='save_location')
def save_location():
    """Saves the robot's current position with a given name."""
    log.info(f"Received request for endpoint '{request.endpoint}' ({request.method} {request.path})")
    robot = getattr(global_config.deck, 'robot', None)
    handler = getattr(global_config.deck, 'handler', None)
    is_connected = getattr(handler, 'is_connected', False) if handler else False
    log.info(f"State check - Robot: {bool(robot)}, Handler: {bool(handler)}, Connected: {is_connected}")

    # Validate hardware state - need connection to get reliable current position
    if not (robot and handler and is_connected):
        log.error("Save location failed: Robot or Handler not ready or not connected.")
        return jsonify({"status": "error", "message": "Robot not ready or not connected"}), 500

    # Get location name from form data
    name = request.form.get('name')
    if not name:
        log.warning("Save location failed: Name not provided.")
        return jsonify({"status": "error", "message": "Location name is required"}), 400 # Bad Request
    log.debug(f"Save location request - Name: {name}")

    try:
        log.debug("Getting current position to save.")
        # Ensure we get the most recent position from the robot
        pos = robot.get_position(update_internal=True)
        if pos is None or not all(pos.get(k) is not None for k in ('x', 'y', 'z')):
             log.error(f"Save location failed: Could not get complete current position. Got: {pos}")
             return jsonify({"status": "error", "message": "Failed to get complete current position from robot"}), 500

        log.info(f"Attempting to save location '{name}' at position: {pos}")
        success = robot.add_location(name, pos['x'], pos['y'], pos['z'])

        if success:
            log.info(f"Location '{name}' saved successfully.")
            # Return the updated list of locations
            return jsonify({"status": "ok", "message": f"Saved location '{name}'", "locations": robot.locations})
        else:
            log.error(f"Robot add_location command returned False for name '{name}'.")
            return jsonify({"status": "error", "message": "Failed to save location on robot"}), 500
    except Exception as e:
        log.exception(f"Exception during save_location for name '{name}'!")
        return jsonify({"status": "error", "message": f"Error saving location: {e}"}), 500

# --- API Route for Homing the Robot ---
@plugin.route('/home', methods=['POST'], endpoint='handle_home')
def home():
    """Sends the home command to the robot."""
    log.info(f"Received request for endpoint '{request.endpoint}' ({request.method} {request.path})")
    robot = getattr(global_config.deck, 'robot', None)
    handler = getattr(global_config.deck, 'handler', None)
    is_connected = getattr(handler, 'is_connected', False) if handler else False
    log.info(f"State check - Robot: {bool(robot)}, Handler: {bool(handler)}, Connected: {is_connected}")

    # Validate hardware state
    if not (robot and handler and is_connected):
        log.error("Home command failed: Robot or Handler not ready or not connected.")
        return jsonify({"status": "error", "message": "Robot not ready or not connected"}), 500

    try:
        log.info("Executing robot.home()")
        success = robot.home()
        if success:
            log.info("Homing successful.")
            # Optionally update internal position after homing
            # robot.get_position(update_internal=True)
            return jsonify({"status": "ok", "message": "Homing command sent successfully"})
        else:
            log.error("Robot home command returned False.")
            return jsonify({"status": "error", "message": "Robot homing command failed"}), 500
    except Exception as e:
        log.exception("Exception during robot.home!")
        return jsonify({"status": "error", "message": f"Error during homing: {e}"}), 500

# --- End of app.py ---