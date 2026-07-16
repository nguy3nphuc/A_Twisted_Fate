"""Entry point thử nghiệm với cơ chế chọn màn cũ của Game."""

from game import Game


def main():
    game = Game()
    game.test_mode = True
    # Giữ state SELECT mặc định: Enter/Space mở chọn phase, phím 1-4 chọn màn.
    game.run()


if __name__ == "__main__":
    main()
