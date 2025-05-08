

"""
Dictionary of commands called with human readable names and their associated GCode command
"""

COMMANDS = {
    # Movement & Setup
    "home_all": {
        "gcode": "G28", "desc": "Home all axes", "params": [],
        "wait_after": True, "send_m400_before_wait": False
    },
    "get_position": {
        "gcode": "M114",
        "desc": "Report current position",
        "params": [],
        "wait_after": True, 
        "send_m400_before_wait": False
    },
    "move": {
        "gcode_base": "G1", "desc": "Move axes",
        "params": ["X", "Y", "Z", "F"],
        "wait_after": True, "send_m400_before_wait": True
    },
    "set_absolute": {
        "gcode": "G90", "desc": "Set absolute positioning", "params": [],
        "wait_after": False
    },
    "set_relative": {
        "gcode": "G91", "desc": "Set relative positioning", "params": [],
        "wait_after": False
    },
    "wait_finish": { # The M400 command itself
        "gcode": "M400", "desc": "Wait for moves", "params": [],
        "wait_after": False
    },
    # Pump (Extruder) Commands
    "set_extruder_relative": {
        "gcode": "M83", "desc": "Set extruder relative", "params": [],
        "wait_after": False
    },
    "set_extruder_absolute": {
        "gcode": "M82", "desc": "Set extruder absolute", "params": [],
        "wait_after": False
    },
    "pump_move": { # Internal command used by run_pump method
        "gcode_base": "G1", "desc": "Move extruder (pump)",
        "params": ["E", "F"],
        "wait_after": True, "send_m400_before_wait": True
    },
    # Sonicator (Fan) Commands
    "fan_on": {
        "gcode": "M106 S255", "desc": "Turn fan ON", "params": [],
        "wait_after": False
    },
    "fan_off": {
        "gcode": "M107", "desc": "Turn fan OFF", "params": [],
        "wait_after": False
    },
    "dwell": {
        "gcode": "G4 P{duration_ms}", "desc": "Pause",
        "params": ["duration_ms"],
        "wait_after": True, "send_m400_before_wait": False
    },
    # Add any other commands here
}