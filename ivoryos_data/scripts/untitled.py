import Main as deck
import time


def untitled():
	deck.robot.home(**{'axes': 'xyz'})
	deck.sonicator.run_for_duration(**{'duration_s': 2.0})