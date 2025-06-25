import requests

session = requests.Session()

class Handler:
    url = "http://206.87.106.30:8000/ivoryos/backend_control/deck.handler"
    def connect(self) -> bool:
        """Opens the serial port and starts the reader thread."""
        return session.post(self.url, data={"hidden_name": "connect", "-> boo": -> boo}).json()

    def disconnect(self):
        """Stops reader thread and closes the serial port."""
        return session.post(self.url, data={"hidden_name": "disconnect"}).json()

    def send_command(self, command_key, **kwargs):
        """Looks up command, sends via Serial, conditionally sends M400,
waits for 'ok' response if wait_after is True."""
        return session.post(self.url, data={"hidden_name": "send_command", "command_key": command_key, "**kwargs": **kwargs}).json()

    def send_raw_gcode(self, gcode_string: str) -> bool:
        """Sends a raw G-code string directly over serial without waiting."""
        return session.post(self.url, data={"hidden_name": "send_raw_gcode", "gcode_string": gcode_string}).json()


class Robot:
    url = "http://206.87.106.30:8000/ivoryos/backend_control/deck.robot"
    def add_location(self, name: str, x: float, y: float, z: float) -> bool:
        """Adds or updates a named location and saves to the JSON file."""
        return session.post(self.url, data={"hidden_name": "add_location", "name": name, "x": x, "y": y, "z": z}).json()

    def apply_initial_config(self) -> bool:
        """Sends the loaded initial G-code commands to the controller."""
        return session.post(self.url, data={"hidden_name": "apply_initial_config", "-> boo": -> boo}).json()

    def get_position(self, update_internal: bool = True) -> dict | None:
        """Sends M114, then reads the queue looking for BOTH the position
report and the 'ok' confirmation.

Args:
    update_internal (bool): If True (default), updates self.current_pos.

Returns:
    dict | None: Dictionary {'x': float, 'y': float, 'z': float, 'e': float}
                 or None if sending/parsing fails or timeout occurs."""
        return session.post(self.url, data={"hidden_name": "get_position", "update_internal": update_internal}).json()

    def home(self, axes: str = 'xyz') -> bool:
        """Homes the specified axes and attempts to update position."""
        return session.post(self.url, data={"hidden_name": "home", "axes": axes}).json()

    def move_relative(self, dx: float = 0, dy: float = 0, dz: float = 0, speed: float | None = None) -> bool:
        """Moves the robot by a relative amount in X, Y, or Z."""
        return session.post(self.url, data={"hidden_name": "move_relative", "dx": dx, "dy": dy, "dz": dz, "speed": speed}).json()

    def move_to(self, x: float, y: float, z: float, speed: float | None = None) -> bool:
        """Moves safely to the target XYZ coordinates."""
        return session.post(self.url, data={"hidden_name": "move_to", "x": x, "y": y, "z": z, "speed": speed}).json()

    def move_to_location(self, name: str, z_offset: float = 0.0, speed: float | None = None) -> bool:
        """Retrieves coordinates for a named location from the loaded dictionary and moves safely to it."""
        return session.post(self.url, data={"hidden_name": "move_to_location", "name": name, "z_offset": z_offset, "speed": speed}).json()

    def move_xy(self, x: float, y: float, speed: float | None = None) -> bool:
        """Moves only the X and Y axes to the specified coordinates."""
        return session.post(self.url, data={"hidden_name": "move_xy", "x": x, "y": y, "speed": speed}).json()

    def move_z(self, z: float, speed: float | None = None) -> bool:
        """Moves only the Z axis to the specified height."""
        return session.post(self.url, data={"hidden_name": "move_z", "z": z, "speed": speed}).json()

    def set_absolute_positioning(self) -> bool:
        """Sets the controller to absolute positioning mode (G90)."""
        return session.post(self.url, data={"hidden_name": "set_absolute_positioning", "-> boo": -> boo}).json()

    def set_relative_positioning(self) -> bool:
        """Sets the controller to relative positioning mode (G91)."""
        return session.post(self.url, data={"hidden_name": "set_relative_positioning", "-> boo": -> boo}).json()


class Pump:
    url = "http://206.87.106.30:8000/ivoryos/backend_control/deck.pump"
    def pump_duration(self, duration_s: float, flowrate_ml_min: float) -> bool:
        """Pumps for a specific duration at a specific rate (positive or negative).

Args:
    duration_s (float): The duration to run the pump in seconds. Must be positive.
    flowrate_ml_min (float): The desired pumping rate in mL/min. Negative pumps backwards.

Returns:
    bool: True if commands were sent successfully."""
        return session.post(self.url, data={"hidden_name": "pump_duration", "duration_s": duration_s, "flowrate_ml_min": flowrate_ml_min}).json()

    def pump_volume(self, volume_ml: float, flowrate_ml_min: float) -> bool:
        """Pumps a specific volume at a specific flowrate.

Args:
    volume_ml (float): Volume to pump in mL (can be negative).
    flowrate_ml_min (float): Desired flowrate magnitude in mL/min (must be > 0).

Returns:
    bool: True if commands were sent successfully."""
        return session.post(self.url, data={"hidden_name": "pump_volume", "volume_ml": volume_ml, "flowrate_ml_min": flowrate_ml_min}).json()


class Sonicator:
    url = "http://206.87.106.30:8000/ivoryos/backend_control/deck.sonicator"
    def run_for_duration(self, duration_s: float) -> bool:
        """Turns the sonicator (fan output) on for a specific duration.

Args:
    duration_s (float): The duration to run the sonicator in seconds.

Returns:
    bool: True if commands were sent successfully (minimal check)."""
        return session.post(self.url, data={"hidden_name": "run_for_duration", "duration_s": duration_s}).json()


handler = Handler()
robot = Robot()
pump = Pump()
sonicator = Sonicator()
