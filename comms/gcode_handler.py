import requests
import time
import sys
import websocket # Requires pip install websocket-client
import threading
import queue
import re

# --- Configuration ---
ESP3D_IP = "192.168.0.1"
ESP3D_HTTP_PORT = 80
ESP3D_WS_PORT = 81 # As identified by user
HTTP_TIMEOUT = 15 # Timeout for sending command via HTTP
WAIT_TIMEOUT = 120 # Max time to wait for command completion
POLL_INTERVAL = 0.1 # Short sleep in wait loops if needed (though queue.get blocks)

# Construct base URLs
BASE_HTTP_URL = f"http://{ESP3D_IP}:{ESP3D_HTTP_PORT}"
WS_URL = f"ws://{ESP3D_IP}:{ESP3D_WS_PORT}/"
COMMAND_ENDPOINT = "/command"

# --- Command Dictionary ---
# wait_after determines IF waiting occurs
# send_m400_before_wait determines IF M400 is sent before that wait
COMMANDS = {
    # Movement & Setup
    "home_all": {
        "gcode": "G28", "desc": "Home all axes", "params": [],
        "wait_after": True, # Yes, wait
        "send_m400_before_wait": False # No M400 needed
    },
    "get_position": {
        "gcode": "M114", "desc": "Report current position", "params": [],
        "wait_after": False, # Let position report come via WS normally
    },
    "move": {
        "gcode_base": "G1", "desc": "Move to specified coordinates (X, Y, Z) at optional speed (F)",
        "params": ["X", "Y", "Z", "F"],
        "wait_after": True, # Yes, wait
        "send_m400_before_wait": True # Yes, send M400 first
    },
    "set_absolute": {
        "gcode": "G90", "desc": "Set positioning to absolute coordinates", "params": [],
        "wait_after": False
    },
    "set_relative": {
        "gcode": "G91", "desc": "Set positioning to relative coordinates", "params": [],
        "wait_after": False
    },
    "wait_finish": { # The M400 command itself
        "gcode": "M400", "desc": "Wait for all moves in planner queue to finish", "params": [],
        "wait_after": False
    },
    # Pump (Extruder) Commands
    "set_extruder_relative": {
        "gcode": "M83", "desc": "Set extruder to relative mode", "params": [],
        "wait_after": False
    },
    "set_extruder_absolute": {
        "gcode": "M82", "desc": "Set extruder to absolute mode", "params": [],
        "wait_after": False
    },
    "pump_move": { # Internal command used by run_pump method
        "gcode_base": "G1", "desc": "Move extruder (pump)",
        "params": ["E", "F"],
        "wait_after": True, # Yes, wait
        "send_m400_before_wait": True # Yes, send M400 first
    },
    # Sonicator (Fan) Commands
    "fan_on": {
        "gcode": "M106 S255", "desc": "Turn fan ON (full speed)", "params": [],
        "wait_after": False
    },
    "fan_off": {
        "gcode": "M107", "desc": "Turn fan OFF", "params": [],
        "wait_after": False
    },
    "dwell": {
        "gcode": "G4 P{duration_ms}", "desc": "Pause for specified milliseconds",
        "params": ["duration_ms"],
        "wait_after": True, # Yes, wait
        "send_m400_before_wait": False # No M400 needed
    },
}

# Renamed class
class GCodeHandler:
    """
    Manages communication with a G-code interpreter (currently ESP3D)
    using HTTP for sending commands and WebSocket for receiving responses.
    Uses command-specific wait logic.
    """
    def __init__(self, http_url, ws_url, commands_dict):
        """Initializes the GCodeHandler."""
        self.http_url = http_url
        self.ws_url = ws_url if ws_url.startswith("ws://") else f"ws://{ws_url}"
        self.commands = commands_dict
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
            # Log updated to reflect generic name but specific protocol for now
            print(f"Connecting to WebSocket at {self.ws_url} using 'arduino' subprotocol (for ESP3D)...")
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
        full_url = self.http_url + COMMAND_ENDPOINT
        params = {'commandText': gcode_command}
        print(f"  [{time.strftime('%H:%M:%S')}] Sending HTTP GET: '{gcode_command}'")
        start_time = time.time()
        try:
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
                if message.lower() == 'ok': # Check if message IS 'ok' (case-insensitive)
                    time_elapsed = time.time() - start_wait_time
                    if time_elapsed < ignore_premature_ok_window:
                        print(f"    [WS Wait DelayOK] Ignoring potentially premature 'ok' received after {time_elapsed:.2f}s.")
                        continue
                    else:
                        print(f"  [{time.strftime('%H:%M:%S')}] Delayed 'ok' received after {time_elapsed:.2f}s.")
                        return True
                elif message.lower().endswith('ok'): # Also handle bundled 'ok' suffix
                     time_elapsed = time.time() - start_wait_time
                     if time_elapsed < ignore_premature_ok_window:
                         print(f"    [WS Wait DelayOK] Ignoring potentially premature 'ok' suffix received after {time_elapsed:.2f}s.")
                         continue
                     else:
                         print(f"  [{time.strftime('%H:%M:%S')}] Delayed 'ok' suffix received after {time_elapsed:.2f}s.")
                         return True

                if message.startswith("PING:") or message.startswith("echo:busy") or message.startswith("ACTIVE_ID:"):
                    continue
            except queue.Empty:
                 if not self.is_connected or (self.ws_thread and not self.ws_thread.is_alive()):
                    print("  Error: WebSocket disconnected or thread stopped while waiting."); return False
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
                if message.startswith("PING:") or message.startswith("echo:busy") or message.startswith("ACTIVE_ID:"):
                    continue
            except queue.Empty:
                 if not self.is_connected or (self.ws_thread and not self.ws_thread.is_alive()):
                    print("  Error: WebSocket disconnected or thread stopped while waiting."); return False
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
        if command_key not in self.commands: print(f"Error: Command key '{command_key}' not found."); return False

        cmd_info = self.commands[command_key]
        final_gcode = ""
        should_wait = cmd_info.get("wait_after", False)
        should_send_m400 = cmd_info.get("send_m400_before_wait", False)

        print(f"\n[{time.strftime('%H:%M:%S')}] Executing command '{command_key}': {cmd_info.get('desc', 'N/A')}")

        # Format G-code
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
                m400_cmd_info = self.commands.get("wait_finish")
                if not m400_cmd_info or "gcode" not in m400_cmd_info: print("Error: 'wait_finish' (M400) not defined."); return False
                m400_gcode = m400_cmd_info["gcode"]
                # Send M400 (currently hardcoded to HTTP)
                if not self._send_http_command(m400_gcode): print(f"  Error sending M400 after '{command_key}'."); return False
                m400_was_sent = True
            else:
                 print(f"  Command requires waiting, but M400 send is skipped for '{command_key}'.")

            # --- Dispatch to correct wait logic ---
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


# --- Main Execution Block ---
if __name__ == "__main__":
    # Use try/finally to ensure disconnect
    handler = None # Renamed variable
    try:
        # Instantiate the renamed class
        handler = GCodeHandler(BASE_HTTP_URL, WS_URL, COMMANDS)
        if handler.connect():
            print("\n--- Running Test Sequence (Command-Specific Wait Logic v2) ---")

            # Call methods on the handler instance
            print("\nTesting 'home_all' (Waits for Position Report)...")
            handler.send_command("home_all")

            print("\nTesting 'get_position' (No Wait)...")
            handler.send_command("get_position")
            time.sleep(1)

            print("\nTesting 'move' (Sends M400, Waits for Delayed 'ok')...")
            handler.send_command("set_absolute")
            if handler.send_command("move", X=50, Y=30, F=3000):
                 print("Move completed successfully.")
            else:
                 print("Move failed.") # Continue testing

            # NOTE: run_pump and run_sonicator would now be called on
            # separate Pump and Sonicator instances which are given the handler.
            # e.g. pump = Pump(handler); pump.run(...)

            print("\nTesting final 'move' (Sends M400, Waits for Delayed 'ok')...")
            handler.send_command("move", X=0, Y=0, F=3000)

            print("\n--- Test Sequence Finished ---")
        else:
            print("Could not connect to G-code handler. Exiting.")

    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected. Disconnecting...")
    finally:
        # Ensure disconnect is attempted even if connect failed or handler not fully initialized
        if handler:
             handler.disconnect()

