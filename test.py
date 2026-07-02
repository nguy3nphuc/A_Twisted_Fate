import pygame
pygame.init()
from game import Game
import traceback


def test_two_player_setup():
    game = Game()
    game.selected_phase = 1
    game.state = "PLAY"
    game.load()

    assert len(game.players) == 2
    assert all(hasattr(player, "hp") for player in game.players)


def test_phase_3():
    game = Game()
    game.selected_phase = 3
    game.state = "PLAY"
    game.load()
    
    # Force boss to spawn
    game.phase_start_time = pygame.time.get_ticks() - 11000
    
    try:
        for i in range(500):
            # simulate events like spawn event
            for event in pygame.event.get():
                if event.type == game.spawn_event:
                    game.spawn_enemy()
            
            # force spawn one enemy to be sure
            if i == 10:
                game.spawn_enemy()
            
            game.update(16)
            game.draw()
        print("No error in Phase 3 game loop with Boss!")
    except Exception as e:
        traceback.print_exc()

if __name__ == '__main__':
    test_two_player_setup()
    test_phase_3()
