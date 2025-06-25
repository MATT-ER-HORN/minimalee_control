import Main as deck
import time


def Test():
	deck.sonicator.run_for_duration(**{'duration_s': 5.0})
	deck.robot.move_xy(**{'speed': '7000', 'x': 0.0, 'y': 0.0})
	deck.robot.move_xy(**{'speed': '7000', 'x': 50.0, 'y': 50.0})