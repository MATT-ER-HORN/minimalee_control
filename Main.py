import os
import sys
import configparser
import traceback
# --- Core Imports ---
from ivoryos.utils.global_config import GlobalConfig
from plugin.app import plugin as plugin_blueprint
import ivoryos
# --- Hardware + Communication ---
from comms.commands import COMMANDS
from comms.wifi_handler import WifiHandler, BASE_HTTP_URL, WS_URL
from comms.serial_handler import SerialHandler
from hardware_modules.robot import Robot
from hardware_modules.pump import Pump
from hardware_modules.sonicator import Sonicator
from hardware_modules.hotplate import Hotplate
# --- Constants ---
CONFIG_FILE = 'config.ini'
LOCATIONS_FILE = 'locations.json'
INIT_GCODE_FILE = 'robot_init.gcode'

if __name__ == "__main__":
    print("--- Starting Nichols Bot Control ---")
    
    # Load config
    config = configparser.ConfigParser(inline_comment_prefixes=';')
    if not os.path.exists(CONFIG_FILE):
        print(f"Config file '{CONFIG_FILE}' not found. Exiting.")
        sys.exit(1)
    config.read(CONFIG_FILE)
    
    # Communication Mode
    comm_mode = config.get('Connection', 'mode', fallback='wifi').lower()
    handler = None
    
    try:
        if comm_mode == 'serial':
            handler = SerialHandler(
                port=config.get('Connection', 'serial_port'),
                baudrate=config.getint('Connection', 'baud_rate'),
                commands_dict=COMMANDS
            )
        elif comm_mode == 'wifi':
            handler = WifiHandler(
                http_url=BASE_HTTP_URL,
                ws_url=WS_URL,
                commands_dict=COMMANDS
            )
        else:
            print(f"Invalid comm mode '{comm_mode}'. Use 'wifi' or 'serial'.")
            sys.exit(1)
        
        # Instantiate hardware
        robot = Robot(
            communicator=handler,
            safe_z=config.getfloat('Robot', 'safe_z', fallback=100.0),
            default_speed=config.getfloat('Robot', 'default_speed', fallback=3000.0),
            locations_filepath=LOCATIONS_FILE,
            init_gcode_filepath=INIT_GCODE_FILE
        )
        pump = Pump(comms=handler, mm_per_ml=config.getfloat('Pump', 'mm_per_ml', fallback=1.0))
        sonicator = Sonicator(comms=handler)
        hotplate = Hotplate(comms=handler, max_temp=config.getfloat('Hotplate', 'max_temp', fallback=150.0))
        
        # Connect and configure
        if not handler.connect():
            print("Failed to connect to handler.")
            sys.exit(1)
        
        if not robot.apply_initial_config():
            print("Failed to apply robot config.")
            handler.disconnect()
            sys.exit(1)
        
        # Assign to global_config
        global_config = GlobalConfig()
        if global_config.deck is None:
            class DeckPlaceholder:
                __name__ = __name__
                __file__ = __file__
            global_config.deck = DeckPlaceholder()
        
        global_config.deck.handler = handler
        global_config.deck.robot = robot
        global_config.deck.pump = pump
        global_config.deck.sonicator = sonicator
        global_config.deck.hotplate = hotplate
        
        # Run IvoryOS with plugin
        print("--- Initialization successful. Launching IvoryOS ---")
        ivoryos.run(__name__, blueprint_plugins=plugin_blueprint)
        
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        sys.exit(1)