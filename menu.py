"""Main menu entry point.

All menu code lives here; visual assets are read from the ``menu/`` folder.
Run this file directly with ``python menu.py`` to preview the menu.
"""

import os
import sys

import pygame

from config import WIDTH, HEIGHT

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None


MENU_DIR = os.path.join(os.path.dirname(__file__), "assets", "menu")


def menu_asset(filename):
    return os.path.join(MENU_DIR, filename)


class VideoPlayer:
    """Small self-contained OpenCV video loader for the book opening effect."""

    def __init__(self, path, target_size):
        if cv2 is None or np is None:
            raise RuntimeError("OpenCV/Numpy is unavailable")
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        self.frames = []
        self.target_size = target_size
        self.fps = 30
        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open video: {path}")
        self.fps = capture.get(cv2.CAP_PROP_FPS) or 30
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, target_size)
            # The source video has a white background around the book.
            diff = np.max(np.abs(frame.astype(np.int16) - 255), axis=2)
            alpha = np.where(diff <= 28, 0, 255).astype(np.uint8)
            rgba = np.dstack((frame, alpha))
            self.frames.append(
                pygame.image.frombuffer(rgba.tobytes(), target_size, "RGBA").convert_alpha()
            )
        capture.release()
        if not self.frames:
            raise RuntimeError("Video contains no frames")


class VideoAnimator:
    def __init__(self, player):
        self.player = player
        self.frame_index = 0
        self.timer = 0.0
        self.playing = False
        self.frame_delay = 1.0 / max(1, player.fps)

    def play(self):
        self.frame_index = 0
        self.timer = 0.0
        self.playing = True

    def update(self, dt):
        if not self.playing:
            return
        self.timer += dt
        while self.timer >= self.frame_delay:
            self.timer -= self.frame_delay
            self.frame_index += 1
            if self.frame_index >= len(self.player.frames):
                self.frame_index = len(self.player.frames) - 1
                self.playing = False
                return

    def frame(self):
        return self.player.frames[self.frame_index]


class FrameButton:
    """Clickable UI frame with code-rendered text, never text baked into art."""

    def __init__(self, center, normal_image, hover_image, text, font):
        self.center = center
        self.normal_image = normal_image
        self.hover_image = pygame.transform.scale_by(hover_image, 1.05)
        self.text = text
        self.font = font
        self.image = normal_image
        self.rect = self.image.get_rect(center=center)
        self.hovered = False

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)
        self.image = self.hover_image if self.hovered else self.normal_image
        self.rect = self.image.get_rect(center=self.center)

    def clicked(self, event, sound=None):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.hovered:
            if sound:
                sound.play()
            return True
        return False

    def draw(self, screen):
        screen.blit(self.image, self.rect)
        shadow = self.font.render(self.text, True, (20, 17, 12))
        label = self.font.render(self.text, True, (248, 239, 198))
        screen.blit(shadow, shadow.get_rect(center=(self.rect.centerx + 2, self.rect.centery + 2)))
        screen.blit(label, label.get_rect(center=self.rect.center))


class MainMenu:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "MAIN"
        self.anim_state = "CLOSED"
        self.selected_hero = None
        self.selected_level = None
        self.open_fallback_timer = 0

        self.title_font = pygame.font.SysFont("Arial", 54, bold=True)
        self.button_font = pygame.font.SysFont("Arial", 19, bold=True)
        self._load_audio()
        self.bg = self._load_image("menu_bg.png", (WIDTH, HEIGHT), alpha=False, fallback=(20, 20, 30))
        self.book_closed = self._load_image("book_closed.png", (200, 340))
        self.book_opened = self._load_image("book_opened.png", (500, 340))
        self.player_one_avatar = self._load_image("avt_p1.png", (140, 265))
        self.player_two_avatar = self._load_image("avt_p2.png", (140, 265))
        self.video = self._load_video()
        self._build_buttons()

    def _load_audio(self):
        self.click_sound = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            click_path = os.path.join(os.path.dirname(__file__), "assets", "audio", "click.wav")
            if os.path.isfile(click_path):
                self.click_sound = pygame.mixer.Sound(click_path)
        except pygame.error:
            pass

    def _load_image(self, filename, size, alpha=True, fallback=(50, 50, 50)):
        try:
            image = pygame.image.load(menu_asset(filename))
            image = image.convert_alpha() if alpha else image.convert()
            return pygame.transform.smoothscale(image, size)
        except pygame.error:
            image = pygame.Surface(size, pygame.SRCALPHA if alpha else 0)
            image.fill(fallback)
            return image

    def _load_video(self):
        try:
            return VideoAnimator(VideoPlayer(menu_asset("open_book.mp4"), (675, 600)))
        except (OSError, RuntimeError, pygame.error):
            return None

    def _build_buttons(self):
        frame = self._load_image("frame_button.png", (180, 56))
        frame_hover = frame.copy()
        frame_hover.fill((35, 35, 18), special_flags=pygame.BLEND_RGB_ADD)
        y = HEIGHT - 80
        left, center, right = WIDTH // 4, WIDTH // 2, WIDTH * 3 // 4
        make = lambda x, text: FrameButton((x, y), frame, frame_hover, text, self.button_font)
        self.buttons = {
            "play": make(left, "START GAME"), "settings": make(center, "SETTING"), "quit": make(right, "QUIT"),
            "open_play": make(left, "PLAY"), "back_char": make(right, "BACK"),
            "forest": make(left, "FOREST"), "dungeon": make(right, "DUNGEON"), "back_map": make(center, "BACK"),
        }

    def _visible_buttons(self):
        if self.anim_state == "CLOSING":
            return ("play", "quit")
        if self.state == "MAIN" and self.anim_state == "CLOSED":
            return ("play", "quit")
        if self.state == "CHAR_SELECT" and self.anim_state == "OPEN":
            return ("open_play", "back_char")
        if self.state == "LEVEL_SELECT" and self.anim_state == "OPEN":
            return ("forest", "dungeon", "back_map")
        return ()

    def _start_opening(self):
        if self.video:
            self.video.play()
            self.anim_state = "VIDEO_PLAYING"
        else:
            self.open_fallback_timer = 280
            self.anim_state = "OPENING"

    def _update_animation(self, dt):
        if self.anim_state == "VIDEO_PLAYING":
            self.video.update(dt)
            if not self.video.playing:
                self.state, self.anim_state = "CHAR_SELECT", "OPEN"
        elif self.anim_state == "OPENING":
            self.open_fallback_timer -= dt
            if self.open_fallback_timer <= 0:
                self.state, self.anim_state = "CHAR_SELECT", "OPEN"
        elif self.anim_state == "CLOSING":
            self.open_fallback_timer -= dt
            if self.open_fallback_timer <= 0:
                self.state, self.anim_state = "MAIN", "CLOSED"
        elif self.anim_state == "FLIP_TO_LEVEL":
            self.open_fallback_timer -= dt
            if self.open_fallback_timer <= 0:
                self.state, self.anim_state = "LEVEL_SELECT", "OPEN"
        elif self.anim_state == "FLIP_TO_CHAR":
            self.open_fallback_timer -= dt
            if self.open_fallback_timer <= 0:
                self.state, self.anim_state = "CHAR_SELECT", "OPEN"

    def _handle_clicks(self, event):
        b = self.buttons
        if self.state == "MAIN" and self.anim_state == "CLOSED":
            if b["play"].clicked(event, self.click_sound):
                self._start_opening()
            elif b["quit"].clicked(event, self.click_sound):
                self.running = False
            return
        if self.state == "CHAR_SELECT" and self.anim_state == "OPEN":
            if b["open_play"].clicked(event, self.click_sound):
                # The two cards represent the fixed co-op party.  Keep return
                # values compatible with callers that expect menu selections.
                self.selected_hero, self.selected_level = "co_op", "map_1"
                self.running = False
            elif b["back_char"].clicked(event, self.click_sound):
                # Return to the exact initial menu state: closed book and
                # immediately usable START GAME / QUIT buttons.
                self.state, self.anim_state = "MAIN", "CLOSED"
            return
        if self.state == "LEVEL_SELECT" and self.anim_state == "OPEN":
            if b["forest"].clicked(event, self.click_sound):
                self.selected_level = "map_1"
                self.running = False
            elif b["dungeon"].clicked(event, self.click_sound):
                self.selected_level = "map_2"
                self.running = False
            elif b["back_map"].clicked(event, self.click_sound):
                self.anim_state, self.open_fallback_timer = "FLIP_TO_CHAR", 280

    def _draw_book(self):
        if self.anim_state == "VIDEO_PLAYING" and self.video:
            image = self.video.frame()
        elif self.anim_state in ("CLOSED", "CLOSING"):
            image = self.book_closed
        else:
            image = self.book_opened
        self.screen.blit(image, image.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40)))

    def _draw_player_avatars(self):
        """Place the two co-op character cards on the left/right book pages."""
        if self.state != "CHAR_SELECT" or self.anim_state != "OPEN":
            return
        page_y = HEIGHT // 2 + 25
        self.screen.blit(self.player_one_avatar, self.player_one_avatar.get_rect(center=(WIDTH // 2 - 122, page_y)))
        self.screen.blit(self.player_two_avatar, self.player_two_avatar.get_rect(center=(WIDTH // 2 + 122, page_y)))

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            mouse_pos = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self._handle_clicks(event)
            self._update_animation(dt)
            visible = self._visible_buttons()
            for key in visible:
                self.buttons[key].update(mouse_pos)

            self.screen.blit(self.bg, (0, 0))
            self._draw_book()
            self._draw_player_avatars()
            for key in visible:
                self.buttons[key].draw(self.screen)
            pygame.display.flip()

        return self.selected_hero, self.selected_level


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Crown & Chaos")
    MainMenu(screen).run()
    pygame.quit()


if __name__ == "__main__":
    main()
