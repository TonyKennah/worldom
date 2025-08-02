# c:/game/worldom/main.py
"""
Main entry point for the Worldom game.
"""
import sys
import os

# This adds the 'src' directory to Python's path
# It allows us to import modules from within the 'src' folder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from game import Game

if __name__ == '__main__':
    game_instance = Game()
    game_instance.run()