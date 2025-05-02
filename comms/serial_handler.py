# comms/serial_handler.py
import serial
import time
import sys
import threading
import queue
from .commands import COMMANDS

class SerialHandler:
    """
    Manages communication with a G-code interpreter (e.g., Marlin)
    over a direct USB Serial connection using pyserial.
    Uses M400 and waits for 'ok' response for synchronization.
    """
    
    DEFAULT_WAIT_TIMEOUT = 120.0 # Default value in seconds

    
    def __init__(self, port: str, baudrate: int, commands_dict: dict,read_timeout: float = 1.0):
        """
        Initializes the SerialHandler.

        Args:
            port (str): The serial port name (e.g., 'COM3' on Windows, '/dev/ttyACM0' on Linux).
            baudrate (int): The serial baud rate (must match firmware config, e.g., 115200, 250000).
            commands_dict (dict): Dictionary defining G-code commands and wait behavior.
            read_timeout (float): Timeout in seconds for reading each line from serial. Defaults to 1.0.
            connect_timeout (float): Timeout in seconds for establishing initial connection (currently informational).
        """
      

        self.port = port
        self.baudrate = baudrate
        self.commands = commands_dict
        self.read_timeout = read_timeout
        self.wait_timeout = self.DEFAULT_WAIT_TIMEOUT

        self.serial_connection = None # Holds the pyserial Serial object
        self.is_connected = False
        self.message_queue = queue.Queue() # Queue for received lines
        self.reader_thread = None # Thread for reading serial
        self.reader_stop_event = threading.Event()

   
    def connect(self) -> bool:
        """Opens the serial port and starts the reader thread."""
        if self.is_connected: return True
        print(f"Attempting to connect to serial port {self.port} at {self.baudrate} baud...")
        try:
            self.serial_connection = serial.Serial(timeout=self.read_timeout)
            self.serial_connection.port = self.port
            self.serial_connection.baudrate = self.baudrate
            self.serial_connection.open()
            time.sleep(2.0)
            self.serial_connection.reset_input_buffer()
            self._clear_queue()
            self.is_connected = True
            self.reader_stop_event.clear()
            self.reader_thread = threading.Thread(target=self._serial_reader_thread, daemon=True)
            self.reader_thread.start()
            print(f"Serial port {self.port} connected.")
            return True
        except serial.SerialException as e:
            print(f"Serial Error: Could not open port {self.port}: {e}")
            self.serial_connection = None; self.is_connected = False; return False
        except Exception as e:
            print(f"Unexpected error connecting to serial port: {e}")
            if self.serial_connection and self.serial_connection.is_open: self.serial_connection.close()
            self.serial_connection = None; self.is_connected = False; return False

    def _serial_reader_thread(self):
        """Runs in background, reads lines from serial, puts them in queue."""
        print("Serial reader thread started.")
        while not self.reader_stop_event.is_set() and self.serial_connection and self.serial_connection.is_open:
            try:
                line_bytes = self.serial_connection.readline()
                if line_bytes:
                    try:
                        line_str = line_bytes.decode('utf-8').strip()
                        if line_str: self.message_queue.put(line_str)
                    except UnicodeDecodeError: print(f"  [Serial Recv] Warning: Could not decode line: {line_bytes!r}")
            except serial.SerialException as e:
                 if not self.reader_stop_event.is_set(): print(f"Serial reader error: {e}")
                 self.is_connected = False; break
            except Exception as e:
                 if not self.reader_stop_event.is_set(): print(f"Unexpected serial reader error: {e}")
                 self.is_connected = False; break
        print("Serial reader thread stopped.")

    def disconnect(self):
        """Stops reader thread and closes the serial port."""
        if self.reader_thread and self.reader_thread.is_alive():
            print("Stopping serial reader thread..."); self.reader_stop_event.set()
        if self.serial_connection and self.serial_connection.is_open:
            print(f"Closing serial port {self.port}...")
            try: self.serial_connection.close()
            except Exception as e: print(f"Error closing serial port: {e}")
        self.is_connected = False; self.serial_connection = None; self.reader_thread = None
        print("Serial disconnected.")

    def _clear_queue(self):
        """Clears any pending messages from the queue."""
        while not self.message_queue.empty():
            try: self.message_queue.get_nowait()
            except queue.Empty: break

    def _send_serial_command(self, gcode_command: str) -> bool:
        """Sends a G-code string over the serial connection."""
        if not self.is_connected or not self.serial_connection or not self.serial_connection.is_open: print("Error: Serial not connected."); return False
        try:
            command_with_newline = (gcode_command + '\n').encode('utf-8')
            print(f"  [{time.strftime('%H:%M:%S')}] Sending Serial: '{gcode_command}'")
            self.serial_connection.write(command_with_newline)
            self.serial_connection.flush()
            return True
        except serial.SerialException as e: print(f"Serial write error: {e}"); self.is_connected = False; return False
        except Exception as e: print(f"Unexpected serial write error: {e}"); return False

    def _wait_for_ok(self) -> bool:
        """
        Waits for an 'ok' response from the serial message queue using self.wait_timeout.
        Returns True if 'ok' received, False on timeout or error.
        """
        # Uses self.wait_timeout defined in __init__
        print(f"  [{time.strftime('%H:%M:%S')}] Waiting for 'ok' response (max {self.wait_timeout}s)...")
        start_wait_time = time.time()

        while time.time() - start_wait_time < self.wait_timeout:
            try:
                message = self.message_queue.get(timeout=1.0)
                print(f"    [Serial Wait] Received: '{message}'")
                if message.lower() == 'ok':
                    print(f"  [{time.strftime('%H:%M:%S')}] 'ok' received.")
                    return True
                if message.startswith("echo:busy"):
                     print("    [Serial Wait] Received busy echo, continuing wait...")
                     continue
            except queue.Empty:
                if not self.is_connected: print("  Error: Serial disconnected while waiting."); return False
                if self.reader_thread is None or not self.reader_thread.is_alive(): print("  Error: Serial reader thread is not running."); return False
                continue
            except Exception as e: print(f"  Error while waiting for serial message: {e}"); return False

        print(f"  [{time.strftime('%H:%M:%S')}] Error: Wait for 'ok' timed out after {self.wait_timeout} seconds.")
        return False # Timeout

    # --- Public Methods ---
    def send_raw_gcode(self, gcode_string: str) -> bool:
        """
        Sends a raw G-code string directly over serial without waiting.
        """
        if not gcode_string or not isinstance(gcode_string, str): print("Error: Invalid G-code string provided."); return False
        return self._send_serial_command(gcode_string.strip())

    def send_command(self, command_key, **kwargs):
        """
        Looks up command, sends via Serial, conditionally sends M400,
        waits for 'ok' response if wait_after is True.
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

        if final_gcode.strip().upper().startswith(("G0", "G1", "G28")): print("*** SAFETY WARNING: Command causes movement! Ensure path clear. ***")

        self._clear_queue() # Clear queue before sending

        if not self._send_serial_command(final_gcode): print(f"Error sending primary command '{command_key}' via Serial."); return False

        wait_success = True
        if should_wait:
            m400_was_sent = False
            if should_send_m400:
                print(f"  Command requires M400. Clearing queue before sending M400...")
                self._clear_queue()
                m400_cmd_info = self.commands.get("wait_finish")
                if not m400_cmd_info or "gcode" not in m400_cmd_info: print("Error: 'wait_finish' (M400) not defined."); return False
                m400_gcode = m400_cmd_info["gcode"]
                if not self._send_serial_command(m400_gcode): print(f"  Error sending M400 after '{command_key}'."); return False
                m400_was_sent = True
            else: print(f"  Command requires waiting, but M400 send is skipped for '{command_key}'.")

            # Wait for the final 'ok' response
            wait_success = self._wait_for_ok() # Calls the internal wait function
            if not wait_success: print(f"Warning: Wait for 'ok' failed for command '{command_key}'.")
        else: print(f"  Command does not require waiting. Proceeding immediately.")

        print(f"[{time.strftime('%H:%M:%S')}] Finished command '{command_key}'. Success: {wait_success}")
        return wait_success

