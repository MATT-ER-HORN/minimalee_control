import requests
import time
import sys
import websocket # Requires pip install websocket-client
import threading
import queue
import re
from .commands import COMMANDS



# --- Configuration (Consider moving to config file loading in Main.py) ---
# These are kept here for now based on the provided code, but loading
# them from config.ini in Main.py and passing them to __init__ is better practice.
ESP3D_IP = "192.168.0.1"
ESP3D_HTTP_PORT = 80
ESP3D_WS_PORT = 81 # Websocket port for ESP3D
HTTP_TIMEOUT = 15 # Timeout for sending command via HTTP
WAIT_TIMEOUT = 120 # Max time to wait for command completion
# POLL_INTERVAL not used in this handler version

# Construct base URLs (can also be passed in __init__)
BASE_HTTP_URL = f"http://{ESP3D_IP}:{ESP3D_HTTP_PORT}"
WS_URL = f"ws://{ESP3D_IP}:{ESP3D_WS_PORT}/"
COMMAND_ENDPOINT = "/command"


class WifiHandler: # Renamed class as per user's code
    """
    Manages communication with an ESP3D device over WiFi
    using HTTP for sending commands and WebSocket for receiving responses.
    Uses command-specific wait logic defined in the passed commands_dict.
    """
    def __init__(self, http_url, ws_url, commands_dict):
        """
        Initializes the WifiHandler (ESP3D specific).

        Args:
            http_url (str): The base URL for HTTP commands (e.g., "http://192.168.0.1:80").
            ws_url (str): The URL for the WebSocket connection (e.g., "ws://192.168.0.1:81/").
            commands_dict (dict): The dictionary defining known G-code commands and wait behavior.
        """
        self.http_url = http_url
        self.ws_url = ws_url if ws_url.startswith("ws://") else f"ws://{ws_url}"
        self.commands = commands_dict # Store the passed-in commands dictionary
        self.ws = None
        self.ws_thread = None
        self.ws_stop_event = threading.Event()
        self.message_queue = queue.Queue()
        self.is_connected = False
        # Pattern for position reports
        self.position_pattern = re.compile(r"X:.*Y:.*Z:", re.IGNORECASE)

    def connect(self):
        """Establishes the WebSocket connection and starts receiver thread."""
        if self.is_connected: return True
        try:
            # Log updated to reflect specific handler type
            print(f"Connecting to ESP3D WebSocket at {self.ws_url} using 'arduino' subprotocol...")
            self.ws = websocket.create_connection(
                self.ws_url, timeout=10, subprotocols=["arduino"]
            )
            self.is_connected = True
            self.ws_stop_event.clear()
            self.ws_thread = threading.Thread(target=self._ws_receiver_thread, daemon=True)
            self.ws_thread.start()
            print("WebSocket connected.")
            time.sleep(0.5); self._clear_queue()
            return True
        except Exception as e:
            print(f"WebSocket connection failed: {e}")
            self.ws = None; self.is_connected = False
            return False

    def _ws_receiver_thread(self):
        """Runs in background, receives WS messages, decodes, puts them in queue."""
        while not self.ws_stop_event.is_set() and self.ws:
            try:
                message = self.ws.recv()
                if message:
                    decoded_message = ""
                    try:
                        if isinstance(message, bytes): decoded_message = message.decode('utf-8').strip()
                        else: decoded_message = message.strip()
                        # Handle potential multi-line messages by splitting
                        if decoded_message:
                             lines = decoded_message.replace('\r\n', '\n').split('\n')
                             for line in lines:
                                 if line.strip(): # Add non-empty lines to queue
                                     self.message_queue.put(line.strip())
                    except UnicodeDecodeError: print(f"  [WS Recv] Warning: Could not decode message as UTF-8: {message}")
                    except Exception as e: print(f"  [WS Recv] Error processing message: {e}")
            except websocket.WebSocketConnectionClosedException:
                if not self.ws_stop_event.is_set(): print("WebSocket connection closed unexpectedly.")
                self.is_connected = False; break
            except websocket.WebSocketTimeoutException: continue
            except Exception as e:
                if not self.ws_stop_event.is_set(): print(f"WebSocket receive error: {e}")
                self.is_connected = False; break
        print("WebSocket receiver thread stopped.")

    def disconnect(self):
        """Stops the receiver thread and closes the WebSocket connection."""
        if self.ws_thread and self.ws_thread.is_alive():
            print("Stopping WebSocket thread..."); self.ws_stop_event.set()
        if self.ws:
            print("Closing WebSocket connection...")
            try: self.ws.close(timeout=3)
            except Exception as e: print(f"Error closing WebSocket: {e}")
        self.is_connected = False; self.ws = None; self.ws_thread = None
        print("Disconnected.")

    def _clear_queue(self):
        """Clears any pending messages from the queue."""
        count = 0
        while not self.message_queue.empty():
            try: self.message_queue.get_nowait(); count += 1
            except queue.Empty: break
        # if count > 0: print(f"  Cleared {count} potentially stale messages from queue.")

    def _send_http_command(self, gcode_command):
        """Sends a G-code command via HTTP GET (ESP3D specific implementation)."""
        # Use self.http_url stored during initialization
        full_url = self.http_url + COMMAND_ENDPOINT
        params = {'commandText': gcode_command}
        print(f"  [{time.strftime('%H:%M:%S')}] Sending HTTP GET: '{gcode_command}'")
        start_time = time.time()
        try:
            # Use HTTP_TIMEOUT constant defined globally (or pass as arg)
            response = requests.get(full_url, params=params, timeout=HTTP_TIMEOUT)
            end_time = time.time()
            print(f"  [{time.strftime('%H:%M:%S')}] HTTP request completed in {end_time - start_time:.2f}s (Status: {response.status_code})")
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"  Error during HTTP send: {e}")
            return False

    # --- Specific Wait Functions ---

    def _wait_for_position_report(self, wait_timeout):
        """ Waits for the position report message (X:Y:Z:) via WebSocket. """
        print(f"  [{time.strftime('%H:%M:%S')}] Waiting for Position Report (max {wait_timeout}s)...")
        start_wait_time = time.time()
        while time.time() - start_wait_time < wait_timeout:
            try:
                message = self.message_queue.get(timeout=1.0)
                print(f"    [WS Wait Pos] Received: '{message}'")
                if self.position_pattern.match(message): # Check if message STARTS with X: Y: Z:
                    print(f"  [{time.strftime('%H:%M:%S')}] Position Report received.")
                    return True
                if message.startswith("PING:") or message.startswith("echo:busy") or message.startswith("ACTIVE_ID:"):
                    continue # Ignore known noise
            except queue.Empty:
                if not self.is_connected or (self.ws_thread and not self.ws_thread.is_alive()):
                    print("  Error: WebSocket disconnected or thread stopped while waiting."); return False
                continue
            except Exception as e: print(f"  Error while waiting for WS message: {e}"); return False
        print(f"  [{time.strftime('%H:%M:%S')}] Error: Wait for Position Report timed out."); return False

    def _wait_for_delayed_ok(self, wait_timeout):
        """ Waits for 'ok' suffix, ignoring premature ones using a time filter. (Used after M400) """
        print(f"  [{time.strftime('%H:%M:%S')}] Waiting for DELAYED 'ok' suffix (max {wait_timeout}s)...")
        start_wait_time = time.time()
        ignore_premature_ok_window = 1.5

        while time.time() - start_wait_time < wait_timeout:
            try:
                message = self.message_queue.get(timeout=1.0)
                print(f"    [WS Wait DelayOK] Received: '{message}'")
                is_ok = message.lower() == 'ok'
                is_ok_suffix = not is_ok and message.lower().endswith('ok') # Check suffix only if not exactly 'ok'
                if is_ok or is_ok_suffix:
                    time_elapsed = time.time() - start_wait_time
                    if time_elapsed < ignore_premature_ok_window: print(f"    [WS Wait DelayOK] Ignoring potentially premature 'ok' received after {time_elapsed:.2f}s."); continue
                    else: print(f"  [{time.strftime('%H:%M:%S')}] Delayed 'ok' received after {time_elapsed:.2f}s."); return True
                if message.startswith("PING:") or message.startswith("echo:busy") or message.startswith("ACTIVE_ID:"): continue
            except queue.Empty:
                 if not self.is_connected or (self.ws_thread and not self.ws_thread.is_alive()): print("  Error: WebSocket disconnected or thread stopped while waiting."); return False
                 continue
            except Exception as e: print(f"  Error while waiting for WS message: {e}"); return False
        print(f"  [{time.strftime('%H:%M:%S')}] Error: Wait for delayed 'ok' suffix timed out."); return False

    def _wait_for_simple_ok(self, wait_timeout):
        """ Waits for the first message that IS 'ok' (case-insensitive). (Used after G4). """
        print(f"  [{time.strftime('%H:%M:%S')}] Waiting for SIMPLE 'ok' (max {wait_timeout}s)...")
        start_wait_time = time.time()
        while time.time() - start_wait_time < wait_timeout:
            try:
                message = self.message_queue.get(timeout=1.0)
                print(f"    [WS Wait SimpleOK] Received: '{message}'")
                if message.lower() == 'ok': # Check if message IS 'ok'
                    print(f"  [{time.strftime('%H:%M:%S')}] Simple 'ok' received.")
                    return True
                if message.startswith("PING:") or message.startswith("echo:busy") or message.startswith("ACTIVE_ID:"): continue
            except queue.Empty:
                 if not self.is_connected or (self.ws_thread and not self.ws_thread.is_alive()): print("  Error: WebSocket disconnected or thread stopped while waiting."); return False
                 continue
            except Exception as e: print(f"  Error while waiting for WS message: {e}"); return False
        print(f"  [{time.strftime('%H:%M:%S')}] Error: Wait for simple 'ok' timed out."); return False

    # Renamed method to be more generic, implementation still ESP3D specific
    def send_command(self, command_key, **kwargs):
        """
        Looks up command, sends (currently via ESP3D HTTP), clears queue,
        conditionally sends M400, calls the appropriate wait function
        based on command type if wait_after is True.
        """
        if not self.is_connected:
            if not self.connect(): print("Error: Cannot send command, connection failed."); return False
        # Use self.commands (passed during init) to find command info
        if command_key not in self.commands: print(f"Error: Command key '{command_key}' not found."); return False

        cmd_info = self.commands[command_key]
        final_gcode = ""
        should_wait = cmd_info.get("wait_after", False)
        should_send_m400 = cmd_info.get("send_m400_before_wait", False)

        print(f"\n[{time.strftime('%H:%M:%S')}] Executing command '{command_key}': {cmd_info.get('desc', 'N/A')}")

        # Format G-code using self.commands
        if "gcode" in cmd_info:
            try: final_gcode = cmd_info["gcode"].format(**kwargs)
            except KeyError as e: print(f"Error: Missing parameter {e} for command '{command_key}'."); return False
            except Exception as e: print(f"Error formatting G-code: {e}"); return False
        elif "gcode_base" in cmd_info:
            final_gcode = cmd_info["gcode_base"]
            for param in cmd_info.get("params", []):
                if param in kwargs: final_gcode += f" {param}{kwargs[param]}"
        else: print("Error: Command definition missing."); return False

        if final_gcode.strip().upper().startswith(("G0", "G1", "G28")):
            print("*** SAFETY WARNING: Command causes movement! Ensure path clear. ***")

        self._clear_queue() # Clear before sending

        # Send the primary command (currently hardcoded to HTTP)
        if not self._send_http_command(final_gcode):
            print(f"Error sending primary command '{command_key}' via HTTP."); return False

        wait_success = True
        if should_wait:
            m400_was_sent = False
            if should_send_m400:
                print(f"  Command requires M400. Clearing queue before sending M400...")
                self._clear_queue()
                # Use self.commands to get M400 info
                m400_cmd_info = self.commands.get("wait_finish")
                if not m400_cmd_info or "gcode" not in m400_cmd_info: print("Error: 'wait_finish' (M400) not defined."); return False
                m400_gcode = m400_cmd_info["gcode"]
                # Send M400 (currently hardcoded to HTTP)
                if not self._send_http_command(m400_gcode): print(f"  Error sending M400 after '{command_key}'."); return False
                m400_was_sent = True
            else:
                 print(f"  Command requires waiting, but M400 send is skipped for '{command_key}'.")

            # --- Dispatch to correct wait logic ---
            # Use WAIT_TIMEOUT constant defined globally (or pass as arg)
            if command_key == "home_all":
                wait_success = self._wait_for_position_report(WAIT_TIMEOUT)
            elif m400_was_sent: # Assumes M400 was sent for moves like G1, pump_move
                 wait_success = self._wait_for_delayed_ok(WAIT_TIMEOUT)
            elif command_key == "dwell": # G4 command
                 wait_success = self._wait_for_simple_ok(WAIT_TIMEOUT)
            else: # Default wait for other commands marked wait_after=True
                 print(f"  Using simple 'ok' wait for '{command_key}'")
                 wait_success = self._wait_for_simple_ok(WAIT_TIMEOUT)

            if not wait_success: print(f"Warning: Wait condition failed for command '{command_key}'.")
        else:
             print(f"  Command does not require waiting. Proceeding immediately.")

        print(f"[{time.strftime('%H:%M:%S')}] Finished command '{command_key}'. Success: {wait_success}")
        return wait_success

    # --- High-Level Methods REMOVED ---
    # Moved to device-specific classes (Pump, Sonicator)


# --- Main Execution Block (Example for testing handler directly) ---
if __name__ == "__main__":
    # This block is for testing the handler itself, if needed.
    # It requires the COMMANDS dictionary to be available.
    print("--- Testing WifiHandler Directly ---")

    # Use the globally defined URLs/COMMANDS for this test block
    # In real use, these should come from config and be passed to __init__
    if not COMMANDS:
         print("Error: COMMANDS dictionary not loaded/defined. Cannot run test.")
         sys.exit(1)

    handler = WifiHandler(BASE_HTTP_URL, WS_URL, COMMANDS)
    try:
        if handler.connect():
            print("\n--- Running Handler Test Sequence ---")

            print("\nTesting 'home_all'...")
            handler.send_command("home_all")
            time.sleep(1)

            print("\nTesting 'move'...")
            handler.send_command("set_absolute")
            handler.send_command("move", X=10, Y=10, F=1000)
            time.sleep(1)

            print("\nTesting 'dwell'...")
            handler.send_command("dwell", duration_ms=2000) # Wait 2 seconds
            time.sleep(1)

            print("\n--- Handler Testing Finished ---")
        else:
            print("Failed to connect handler.")
    except KeyboardInterrupt:
        print("\nKeyboard interrupt.")
    finally:
        if handler:
            handler.disconnect()

