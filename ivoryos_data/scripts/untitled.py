import Main as deck
import time


def untitled():
	deck.robot.home(**{'axes': 'xyz'})
	deck.pump.pump_duration(**{'duration_s': 3.0, 'flowrate_ml_min': 50.0})
	deck.sonicator.run_for_duration(**{'duration_s': 5.0})