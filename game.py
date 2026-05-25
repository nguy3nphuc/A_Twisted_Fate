import pygame
import sys
import random
from config import WIDTH, HEIGHT, FPS, MAP_IMAGE, MIN_Y, MAX_Y
from entities import Knight, Archer, Enemy


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Beat-em-up Test")
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "SELECT"
        self.selected_hero = 'knight'

        # Try load map
        try:
            self.map = pygame.image.load(MAP_IMAGE).convert()
        except Exception:
            self.map = pygame.Surface((WIDTH, HEIGHT))
            self.map.fill((50, 150, 50))
            
        self.knight_preview = Knight(pos=(WIDTH//3, HEIGHT//2 + 50))
        self.archer_preview = Archer(pos=(2*WIDTH//3, HEIGHT//2 + 50))

    def load(self):
        # sprite groups
        self.all_sprites = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.attacks = pygame.sprite.Group()
        self.arrows = pygame.sprite.Group()

        self.groups = {'all': self.all_sprites, 'enemies': self.enemies, 'attacks': self.attacks, 'arrows': self.arrows}

        # Player (start slightly above the bottom boundary)
        if self.selected_hero == 'knight':
            self.player = Knight(pos=(WIDTH//2, HEIGHT-100))
        else:
            self.player = Archer(pos=(WIDTH//2, HEIGHT-100))
            
        self.all_sprites.add(self.player)

        # spawn timer
        self.spawn_event = pygame.USEREVENT + 1
        pygame.time.set_timer(self.spawn_event, 1500)

    def spawn_enemy(self):
        side = random.choice(['left', 'right'])
        y = random.randint(MIN_Y + 50, MAX_Y - 30)
        x = -40 if side == 'left' else WIDTH + 40
        enemy = Enemy(pos=(x, y))
        self.enemies.add(enemy)
        self.all_sprites.add(enemy)

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)
            if self.state == "SELECT":
                self.events_select()
                self.update_select(dt)
                self.draw_select()
            else:
                self.events()
                self.update(dt)
                self.draw()
        pygame.quit()
        sys.exit()

    def events_select(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    self.selected_hero = 'knight'
                    self.state = "PLAY"
                    self.load()
                elif event.key == pygame.K_2:
                    self.selected_hero = 'archer'
                    self.state = "PLAY"
                    self.load()

    def update_select(self, dt):
        self.knight_preview.update(dt, keys=None, groups=None)
        self.archer_preview.update(dt, keys=None, groups=None)

    def draw_select(self):
        self.screen.blit(self.map, (0, 0))
        
        font = pygame.font.SysFont('Arial', 48, bold=True)
        text = font.render("Select Your Hero", True, (255, 255, 255))
        self.screen.blit(text, text.get_rect(center=(WIDTH // 2, 100)))

        font_sub = pygame.font.SysFont('Arial', 32)
        text_k = font_sub.render("Press 1 for Knight", True, (255, 255, 255))
        self.screen.blit(text_k, text_k.get_rect(center=(WIDTH // 3, HEIGHT // 2 + 100)))
        
        text_a = font_sub.render("Press 2 for Archer", True, (255, 255, 255))
        self.screen.blit(text_a, text_a.get_rect(center=(2 * WIDTH // 3, HEIGHT // 2 + 100)))

        self.screen.blit(self.knight_preview.image, self.knight_preview.rect)
        self.screen.blit(self.archer_preview.image, self.archer_preview.rect)
        
        pygame.display.flip()

    def events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == self.spawn_event:
                if self.player.hp > 0:
                    self.spawn_enemy()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r and self.player.hp <= 0:
                    self.state = "SELECT"

    def update(self, dt):
        keys = pygame.key.get_pressed()
        # update player
        self.player.update(dt, keys, self.groups)

        # update enemies
        for e in list(self.enemies):
            e.update(dt, self.player, self.groups)

        # update attacks
        self.attacks.update(dt)
        self.arrows.update(dt)

        # collisions: attack hitboxes vs enemies
        # Use dokill=False for attacks first, then manually kill valid hits
        # so attacks don't get wasted on dead enemies
        hits = pygame.sprite.groupcollide(self.enemies, self.attacks, False, False)
        for enemy, hitboxes in hits.items():
            if enemy.hp <= 0:
                continue  # skip dead enemies — don't waste attacks on corpses
            for hb in hitboxes:
                enemy.take_damage(hb.damage, source_x=hb.rect.centerx)
                hb.kill()  # consume the hitbox after applying damage

        # collisions: arrows vs enemies
        arrow_hits = pygame.sprite.groupcollide(self.enemies, self.arrows, False, True)
        for enemy, arrows_hit in arrow_hits.items():
            if enemy.hp <= 0:
                continue
            for arrow in arrows_hit:
                enemy.take_damage(arrow.damage, source_x=arrow.rect.centerx)

        # collisions: enemy touching player already handled in enemy.update

    def draw(self):
        self.screen.blit(self.map, (0, 0))
        # Draw sprites sorted by Y position (rect.bottom) for depth ordering.
        # Entities closer to the bottom of the screen appear in front,
        # creating a "Mighty Knight"-style pseudo-3D depth effect.
        sorted_sprites = sorted(self.all_sprites, key=lambda s: s.rect.bottom)
        for sprite in sorted_sprites:
            self.screen.blit(sprite.image, sprite.rect)
        for hb in self.attacks:
            self.screen.blit(hb.image, hb.rect)
        for arrow in self.arrows:
            self.screen.blit(arrow.image, arrow.rect)

        # HUD: player HP
        self.draw_health_bar(self.player.hp, self.player.max_hp)

        # GAME OVER UI
        if self.player.hp <= 0:
            font = pygame.font.SysFont('Arial', 64, bold=True)
            text = font.render("GAME OVER", True, (255, 0, 0))
            text_rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 50))
            self.screen.blit(text, text_rect)
            
            font_sub = pygame.font.SysFont('Arial', 32)
            sub_text = font_sub.render("Press 'R' to Restart", True, (255, 255, 255))
            sub_rect = sub_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30))
            self.screen.blit(sub_text, sub_rect)

        pygame.display.flip()

    def draw_health_bar(self, hp, max_hp):
        w = 200
        h = 16
        x = 10
        y = 10
        ratio = max(0, hp) / max_hp
        pygame.draw.rect(self.screen, (60, 60, 60), (x - 2, y - 2, w + 4, h + 4))
        pygame.draw.rect(self.screen, (200, 0, 0), (x, y, w, h))
        pygame.draw.rect(self.screen, (0, 200, 0), (x, y, int(w * ratio), h))
