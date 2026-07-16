"""Main entry point: show the menu, then start the four-phase campaign."""

import pygame

from config import WIDTH, HEIGHT
from game import Game
from menu import MainMenu


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Crown & Chaos")

    selected_hero, selected_level = MainMenu(screen).run()
    if not selected_hero or not selected_level:
        pygame.quit()
        return

    game = Game()
    game.start_campaign()
    game.run()


if __name__ == "__main__":
    main()
