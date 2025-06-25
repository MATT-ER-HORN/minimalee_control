import Main as deck
import time


def robot_movement_demo():
	deck.robot.move_to_location(**{'name': '1', 'speed': '7000', 'z_offset': 0.0})
	deck.robot.move_to_location(**{'name': '2', 'speed': '7000', 'z_offset': 0.0})
	deck.robot.move_to_location(**{'name': '3', 'speed': '10000', 'z_offset': 0.0})