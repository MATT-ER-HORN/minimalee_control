
import time
import sys
import os
from comms.gcode_handler import GCodeHandler, COMMANDS, BASE_HTTP_URL, WS_URL
from hardware_modules.sonicator import Sonicator


# --- Configuration (Assuming imported/defined in gcode_handler) ---
# If URLs/COMMANDS are loaded from config.ini, add loading logic here.
# Example:
# config = configparser.ConfigParser()
# config.read('config.ini')
# BASE_HTTP_URL = config.get('Connection', 'http_url', fallback='http://192.168.0.1:80')
# WS_URL = config.get('Connection', 'ws_url', fallback='ws://192.168.0.1:81/')
# Note: COMMANDS dictionary might be complex to store/load from INI

# --- Main Execution ---
if __name__ == "__main__":
    print("--- Sonicator Test Script ---")

    # Instantiate handler (assuming URLs/COMMANDS are imported/available)
    # Provide the necessary arguments loaded from config or defined globally
    handler = GCodeHandler(BASE_HTTP_URL, WS_URL, COMMANDS)
    # Instantiate sonicator, passing the handler instance
    sonicator = Sonicator(comms=handler)

    try:
        print("\nAttempting to connect...")
        # Connect the handler (essential step)
        if handler.connect():
            print("\n--- Running Sonicator Tests ---")

            # --- Your Test Sequence ---
            print("\n--- Test 1: Sonicate for 5 seconds ---")
            success1 = sonicator.sonicate_duration(sonicate_sec=5.0)
            print(f"Test 1 Result: {success1}")
            time.sleep(1) # Pause between tests for observation

            print("\n--- Sonicator Testing Finished ---")
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

