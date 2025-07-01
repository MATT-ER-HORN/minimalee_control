import Main as deck
import time


def untitled_prep():
	deck.pump.pump_volume(**{'flowrate_ml_min': 40.0, 'volume_ml': 3.0})
	deck.hotplate.heat_and_wait(**{'target_temp': 80.0, 'timeout_s': 600.0})