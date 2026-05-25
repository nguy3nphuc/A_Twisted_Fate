import pygame
import time
import os
import random
from sprites import SpriteSheet, Animator, load_frames_from_folder
from config import (PLAYER_SPRITESHEET, ENEMY_SPRITESHEET, MIN_Y, MAX_Y, MIN_X, MAX_X,
                     PLAYER_ATTACK_WIDTH, PLAYER_ATTACK_HEIGHT, PLAYER_ATTACK_OFFSET_X,
                     ENEMY_ATTACK_RANGE_X, ENEMY_ATTACK_RANGE_Y,
                     DEATH_FADE_DELAY, DEATH_FADE_DURATION, ARCHER_DIR, ARROW_IMAGE)


class HealthMixin:
    def __init__(self, max_hp):
        self.max_hp = max_hp
        self.hp = max_hp

    def take_damage(self, amount):
        # ignore damage if already dead
        if self.hp <= 0:
            return
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()

    def on_death(self):
        self.kill()


class AttackHitbox(pygame.sprite.Sprite):
    def __init__(self, owner, rect, damage=10, duration=150):
        super().__init__()
        self.owner = owner
        self.image = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
        self.image.fill((255, 0, 0, 80))
        self.rect = pygame.Rect(rect)
        self.damage = damage
        self.spawn_time = pygame.time.get_ticks()
        self.duration = duration

    def update(self, dt):
        if pygame.time.get_ticks() - self.spawn_time > self.duration:
            self.kill()


class Knight(pygame.sprite.Sprite, HealthMixin):
    def __init__(self, pos=(200, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=100)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.vel = pygame.math.Vector2(0, 0)
        self.speed = 4
        self.facing = 1
        self.on_ground = True
        self.attack_cooldown = 0
        self.hurt_timer = 0
        self.combo_step = 0
        self.combo_buffered = False
        self.exceeded_combo = False
        self.combo_break_timer = 0
        self.attack_pressed_last = False
        self.has_attacked = False # flag to ensure damage is dealt only once at midpoint

    def load_assets(self):
        w, h = 64, 64
        scale = 2.8
        # prefer a single spritesheet if present
        if os.path.exists(PLAYER_SPRITESHEET):
            ss = SpriteSheet(PLAYER_SPRITESHEET)
            try:
                idle = ss.load_strip((0, 0, w, h), 4)
                run = ss.load_strip((0, h, w, h), 6)
                attack1 = ss.load_strip((0, h * 2, w, h), 4)
                attack2 = ss.load_strip((0, h * 2, w, h), 4)
                attack3 = ss.load_strip((0, h * 2, w, h), 4)
                hit = ss.load_strip((0, h * 3, w, h), 2)
                death = ss.load_strip((0, h * 4, w, h), 4)
                defend = ss.load_strip((0, h * 5, w, h), 4) # Assuming defend is row 5 if spritesheet used
                if scale != 1.0:
                    idle = [pygame.transform.scale(f, (int(w * scale), int(h * scale))) for f in idle]
                    run = [pygame.transform.scale(f, (int(w * scale), int(h * scale))) for f in run]
                    attack1 = [pygame.transform.scale(f, (int(w * scale), int(h * scale))) for f in attack1]
                    attack2 = [pygame.transform.scale(f, (int(w * scale), int(h * scale))) for f in attack2]
                    attack3 = [pygame.transform.scale(f, (int(w * scale), int(h * scale))) for f in attack3]
                    hit = [pygame.transform.scale(f, (int(w * scale), int(h * scale))) for f in hit]
                    death = [pygame.transform.scale(f, (int(w * scale), int(h * scale))) for f in death]
                    defend = [pygame.transform.scale(f, (int(w * scale), int(h * scale))) for f in defend]
            except Exception:
                idle = [pygame.Surface((int(w * scale), int(h * scale)))]
                run = [pygame.Surface((int(w * scale), int(h * scale)))]
                attack1 = [pygame.Surface((int(w * scale), int(h * scale)))]
                attack2 = [pygame.Surface((int(w * scale), int(h * scale)))]
                attack3 = [pygame.Surface((int(w * scale), int(h * scale)))]
                hit = [pygame.Surface((int(w * scale), int(h * scale)))]
                death = [pygame.Surface((int(w * scale), int(h * scale)))]
                defend = [pygame.Surface((int(w * scale), int(h * scale)))]
        else:
            # try loading from folder individual frames like IDLE.png, RUN.png, ATTACK 1.png...
            folder = os.path.dirname(PLAYER_SPRITESHEET)
            idle = load_frames_from_folder(folder, 'IDLE', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
            run = load_frames_from_folder(folder, 'RUN', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
            attack1 = load_frames_from_folder(folder, 'ATTACK 1', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
            attack2 = load_frames_from_folder(folder, 'ATTACK 2', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
            attack3 = load_frames_from_folder(folder, 'ATTACK 3', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
            hit = load_frames_from_folder(folder, 'HURT', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
            death = load_frames_from_folder(folder, 'DEATH', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
            defend = load_frames_from_folder(folder, 'DEFEND', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]

        if len(defend) > 2:
            defend_idle = defend[:2]
            defend_hit = defend[2:] + defend[:2]
        else:
            defend_idle = defend
            defend_hit = defend

        frames = {
            'idle': idle,
            'run': run,
            'attack1': attack1,
            'attack2': attack2,
            'attack3': attack3,
            'hit': hit,
            'death': death,
            'defend_idle': defend_idle,
            'defend_hit': defend_hit
        }
        durations = {
            'idle': 150,
            'run': 100,
            'attack1': 70,
            'attack2': 70,
            'attack3': 70,
            'hit': 100,
            'death': 100,
            'defend_idle': 150,
            'defend_hit': 80
        }
        loop_states = {'idle', 'run'}
        self.animator = Animator(frames, durations, default_state='idle', loop_states=loop_states)

    def take_damage(self, amount, source_x=None):
        if self.hp <= 0:
            return
            
        is_defending = getattr(self, 'animator', None) is not None and self.animator.state in ('defend_idle', 'defend_hit')
        hit_from_front = False
        
        if is_defending and source_x is not None:
            if self.facing == 1 and source_x > self.rect.centerx:
                hit_from_front = True
            elif self.facing == -1 and source_x < self.rect.centerx:
                hit_from_front = True
                
        if hit_from_front:
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('defend_hit', reset=True)
            self.vel.x = -self.facing * 1
            return
            
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        else:
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            self.vel.x = -self.facing * 3
            self.hurt_timer = 300
            self.combo_step = 0
            self.combo_buffered = False
            self.exceeded_combo = False

    def update(self, dt, keys=None, groups=None):
        if keys is None or groups is None:
            return

        # check if dead
        if self.hp <= 0:
            if getattr(self, 'animator', None) is not None:
                self.animator.update(dt)
                mid = self.rect.midbottom
                frame = self.animator.get_frame()
                if self.facing == -1:
                    frame = pygame.transform.flip(frame, True, False)
                self.image = frame
                self.rect = self.image.get_rect(midbottom=mid)
            return

        # handle timers
        if self.combo_break_timer > 0:
            self.combo_break_timer -= dt

        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.8
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            
            if self.hurt_timer <= 0:
                if getattr(self, 'animator', None) is not None:
                    self.animator.set_state('idle', reset=False)
            else:
                if getattr(self, 'animator', None) is not None:
                    self.animator.update(dt)
                    mid = self.rect.midbottom
                    frame = self.animator.get_frame()
                    if self.facing == -1:
                        frame = pygame.transform.flip(frame, True, False)
                    self.image = frame
                    self.rect = self.image.get_rect(midbottom=mid)
                return

        self.handle_input(keys, groups)
        
        self.rect.x += int(self.vel.x)
        self.rect.y += int(self.vel.y)

        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt

        # choose animation state
        if getattr(self, 'animator', None) is not None:
            if self.animator.state in ('attack1', 'attack2', 'attack3'):
                # Check for midpoint to spawn hitbox
                if self.animator.is_midpoint() and not self.has_attacked:
                    self.spawn_attack_hitbox(groups)
                    self.has_attacked = True

                if self.animator.is_finished():
                    if self.combo_step == 1 and self.combo_buffered:
                        self.start_combo_step(2, groups)
                    elif self.combo_step == 2 and self.combo_buffered:
                        self.start_combo_step(3, groups)
                    else:
                        if self.combo_step == 3 or getattr(self, 'exceeded_combo', False):
                            self.combo_break_timer = 800
                        self.combo_step = 0
                        self.combo_buffered = False
                        self.exceeded_combo = False
                        self.animator.set_state('idle', reset=False)
            elif self.animator.state == 'defend_hit':
                if self.animator.is_finished():
                    if keys[pygame.K_k]:
                        self.animator.set_state('defend_idle', reset=True)
                    else:
                        self.animator.set_state('idle', reset=False)
            elif self.animator.state == 'defend_idle':
                if not keys[pygame.K_k]:
                    self.animator.set_state('idle', reset=False)
            else:
                if keys[pygame.K_k]:
                    self.animator.set_state('defend_idle', reset=True)
                    self.vel.x = 0
                    self.vel.y = 0
                elif abs(self.vel.x) > 0 or abs(self.vel.y) > 0:
                    self.animator.set_state('run', reset=False)
                else:
                    self.animator.set_state('idle', reset=False)
            self.animator.update(dt)
            mid = self.rect.midbottom
            frame = self.animator.get_frame()
            if self.facing == -1:
                frame = pygame.transform.flip(frame, True, False)
            self.image = frame
            self.rect = self.image.get_rect(midbottom=mid)

        # Clamp position AFTER animation rect update so bounds are always enforced.
        # This uses rect.bottom for Y since that represents the character's feet.
        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))

    def handle_input(self, keys, groups):
        self.vel.x = 0
        self.vel.y = 0
        
        attack_pressed = keys[pygame.K_j]
        just_pressed_attack = attack_pressed and not getattr(self, 'attack_pressed_last', False)
        self.attack_pressed_last = attack_pressed

        if self.combo_break_timer > 0:
            return

        is_attacking = self.animator.state in ('attack1', 'attack2', 'attack3')
        is_defending = getattr(self, 'animator', None) is not None and self.animator.state in ('defend_idle', 'defend_hit')

        if just_pressed_attack:
            if not is_attacking and not is_defending:
                self.start_combo_step(1, groups)
            elif is_attacking:
                if self.animator.state == 'attack1' and self.combo_step == 1:
                    self.combo_buffered = True
                elif self.animator.state == 'attack2' and self.combo_step == 2:
                    self.combo_buffered = True
                elif self.animator.state == 'attack3' and self.combo_step == 3:
                    self.exceeded_combo = True

        if is_attacking or is_defending:
            return

        if keys[pygame.K_k]:
            return

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vel.x = -self.speed
            self.facing = -1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vel.x = self.speed
            self.facing = 1
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.vel.y = -self.speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.vel.y = self.speed

    def start_combo_step(self, step, groups):
        self.combo_step = step
        self.combo_buffered = False
        self.has_attacked = False
        
        state_name = f'attack{step}'
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state(state_name, reset=True)

    def spawn_attack_hitbox(self, groups):
        # Spawn scaled hitbox at the midpoint of the animation
        # Size can be manually adjusted in config.py (PLAYER_ATTACK_WIDTH, HEIGHT, OFFSET_X)
        step = self.combo_step
        damage = 15 + step * 5
        w = PLAYER_ATTACK_WIDTH
        h = PLAYER_ATTACK_HEIGHT
        offset = PLAYER_ATTACK_OFFSET_X
        
        if self.facing == 1:
            rect = (self.rect.centerx + offset, self.rect.centery - h // 2, w, h)
        else:
            rect = (self.rect.centerx - offset - w, self.rect.centery - h // 2, w, h)
        
        hitbox = AttackHitbox(self, rect, damage=damage, duration=100)
        groups['attacks'].add(hitbox)

    def on_death(self):
        print('Player died')
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0


class Enemy(pygame.sprite.Sprite, HealthMixin):
    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=40)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.speed = 1.2
        self.facing = -1
        self.attack_timer = 0
        self.vel = pygame.math.Vector2(0, 0)
        self.hurt_timer = 0
        self.ai_state = 'chase'
        self.ai_timer = 0
        self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
        self.has_attacked = False
        # Death fade-out state
        self.dying = False          # True once death anim finishes
        self.death_fade_timer = 0   # counts up from 0 after death anim
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255

    def load_assets(self):
        w, h = 64, 64
        scale = 3.5
        if os.path.exists(ENEMY_SPRITESHEET):
            ss = SpriteSheet(ENEMY_SPRITESHEET)
            try:
                idle = ss.load_strip((0, 0, w, h), 4)
                run = ss.load_strip((0, h, w, h), 4)
                attack = ss.load_strip((0, h * 2, w, h), 4)
                hit = ss.load_strip((0, h * 3, w, h), 2)
                death = ss.load_strip((0, h * 4, w, h), 4)
                if scale != 1.0:
                    idle = [pygame.transform.scale(f, (int(w * scale), int(h * scale))) for f in idle]
                    run = [pygame.transform.scale(f, (int(w * scale), int(h * scale))) for f in run]
                    attack = [pygame.transform.scale(f, (int(w * scale), int(h * scale))) for f in attack]
                    hit = [pygame.transform.scale(f, (int(w * scale), int(h * scale))) for f in hit]
                    death = [pygame.transform.scale(f, (int(w * scale), int(h * scale))) for f in death]
            except Exception:
                idle = [pygame.Surface((int(w * scale), int(h * scale)))]
                run = [pygame.Surface((int(w * scale), int(h * scale)))]
                attack = [pygame.Surface((int(w * scale), int(h * scale)))]
                hit = [pygame.Surface((int(w * scale), int(h * scale)))]
                death = [pygame.Surface((int(w * scale), int(h * scale)))]
        else:
            folder = os.path.dirname(ENEMY_SPRITESHEET)
            idle = load_frames_from_folder(folder, 'IDLE', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
            run = load_frames_from_folder(folder, 'RUN', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
            attack = load_frames_from_folder(folder, 'ATTACK', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
            hit = load_frames_from_folder(folder, 'HIT', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
            death = load_frames_from_folder(folder, 'DEATH', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]

        frames = {'idle': idle, 'run': run, 'attack': attack, 'hit': hit, 'death': death}
        durations = {'idle': 150, 'run': 100, 'attack': 80, 'hit': 100, 'death': 100}
        loop_states = {'idle', 'run'}
        self.animator = Animator(frames, durations, default_state='idle', loop_states=loop_states)

    def take_damage(self, amount, source_x=None):
        if self.hp <= 0:
            return
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        else:
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            # Knock back away from the damage source
            if source_x is not None:
                knockback_dir = 1 if self.rect.centerx > source_x else -1
            else:
                knockback_dir = -self.facing
            self.vel.x = knockback_dir * 2
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        # Handle death state first
        if self.hp <= 0 or self.animator.state == 'death':
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)
            # NOTE: we do NOT remove from enemies group here — otherwise
            # the game loop stops calling update() and the animation freezes.
            # Collision guarding is handled in game.py instead.

            if not self.dying:
                # Still playing death animation frames
                self.update_animation(dt)
                if self.animator.is_finished():
                    self.dying = True
                    self.death_fade_timer = 0
            else:
                # Death animation done — wait, then fade out
                self.death_fade_timer += dt
                if self.death_fade_timer > self.death_fade_delay:
                    # Fade out over DEATH_FADE_DURATION ms
                    fade_progress = (self.death_fade_timer - self.death_fade_delay) / self.death_fade_duration
                    self.alpha = max(0, int(255 * (1.0 - fade_progress)))
                    self._apply_alpha()
                    if self.alpha <= 0:
                        self.kill()
            return

        # Handle hurt timer next
        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.8
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
            
            if self.hurt_timer <= 0:
                if getattr(self, 'animator', None) is not None:
                    self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        # Handle normal attack state
        if self.animator.state == 'attack':
            # Check for midpoint to deal damage
            if self.animator.is_midpoint() and not self.has_attacked:
                # Deal damage to player if in range (uses configurable constants)
                dist_x = player.rect.centerx - self.rect.centerx
                dist_y = player.rect.bottom - self.rect.bottom
                if abs(dist_x) <= ENEMY_ATTACK_RANGE_X and abs(dist_y) <= ENEMY_ATTACK_RANGE_Y:
                    player.take_damage(10, source_x=self.rect.centerx)
                self.has_attacked = True
            
            self.update_animation(dt)
            if self.animator.is_finished():
                self.animator.set_state('idle', reset=False)
                self.ai_state = 'wait' # take a small break after attack
                self.ai_timer = random.randint(500, 1000)
            return

        # AI Behavior State Machine
        self.ai_timer -= dt
        
        if self.ai_state == 'wait':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
                # set a new random offset for the next chase phase
                self.target_offset = pygame.math.Vector2(random.randint(-50, 50), random.randint(-25, 25))
            self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return
            
        if self.ai_state == 'idle':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
            self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        # CHASE state logic
        moving = False
        self.vel.x = 0
        self.vel.y = 0
        if player is not None and player.hp > 0:
            # target a point near the player for a "random path" feel
            target_x = player.rect.centerx + self.target_offset.x
            target_y = player.rect.bottom + self.target_offset.y
            
            dist_x = target_x - self.rect.centerx
            dist_y = target_y - self.rect.bottom
            
            # Distance to REAL player for attack check
            real_dist_x = player.rect.centerx - self.rect.centerx
            real_dist_y = player.rect.bottom - self.rect.bottom
            
            # Use configurable attack range constants
            range_x = ENEMY_ATTACK_RANGE_X
            range_y = ENEMY_ATTACK_RANGE_Y
            
            # if not close enough to attack
            if abs(real_dist_x) > range_x or abs(real_dist_y) > range_y:
                if abs(dist_x) > 5:
                    if dist_x < 0:
                        self.rect.x -= self.speed
                        self.facing = -1
                    else:
                        self.rect.x += self.speed
                        self.facing = 1
                    moving = True
                if abs(dist_y) > 5:
                    if dist_y < 0:
                        self.rect.y -= self.speed
                    else:
                        self.rect.y += self.speed
                    moving = True
                
                # Occasional idle break while chasing
                if random.random() < 0.005: # small chance every frame
                    self.ai_state = 'idle'
                    self.ai_timer = random.randint(1000, 2000)
            else:
                # in range to attack!
                if pygame.time.get_ticks() - self.attack_timer > 1500:
                    self.animator.set_state('attack', reset=True)
                    self.has_attacked = False
                    self.attack_timer = pygame.time.get_ticks()

        if moving:
            self.animator.set_state('run', reset=False)
        else:
            if self.animator.state not in ('attack', 'hit', 'death'):
                self.animator.set_state('idle', reset=False)

        # Clamp enemy position to the same playable area as the player
        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))

        self.update_animation(dt)

    def update_animation(self, dt):
        if getattr(self, 'animator', None) is not None:
            self.animator.update(dt)
            mid = self.rect.midbottom
            frame = self.animator.get_frame()
            if self.facing == -1:
                frame = pygame.transform.flip(frame, True, False)
            self.image = frame
            self.rect = self.image.get_rect(midbottom=mid)

    def _apply_alpha(self):
        """Apply current alpha to the sprite image for fade-out effect.
        Uses BLEND_RGBA_MULT because per-pixel alpha surfaces ignore set_alpha().
        """
        if self.image is not None:
            faded = self.image.copy()
            # Multiply every pixel's alpha by (self.alpha / 255)
            faded.fill((255, 255, 255, self.alpha), special_flags=pygame.BLEND_RGBA_MULT)
            self.image = faded

    def on_death(self):
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0


class Arrow(pygame.sprite.Sprite):
    ARROW_SCALE = 2.5  # match the archer's sprite scale

    def __init__(self, x, y, facing, damage=15):
        super().__init__()
        try:
            raw = pygame.image.load(ARROW_IMAGE).convert_alpha()
            aw = int(raw.get_width() * self.ARROW_SCALE)
            ah = int(raw.get_height() * self.ARROW_SCALE)
            self.image = pygame.transform.scale(raw, (aw, ah))
        except Exception:
            self.image = pygame.Surface((65, 8))
            self.image.fill((200, 200, 200))

        if facing == -1:
            self.image = pygame.transform.flip(self.image, True, False)

        self.rect = self.image.get_rect(center=(x, y))
        self.facing = facing
        self.speed = 12
        self.damage = damage

    def update(self, dt):
        self.rect.x += self.speed * self.facing
        if self.rect.right < 0 or self.rect.left > MAX_X:
            self.kill()


class Archer(pygame.sprite.Sprite, HealthMixin):
    def __init__(self, pos=(200, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=80)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.vel = pygame.math.Vector2(0, 0)
        self.speed = 5
        self.facing = 1
        self.on_ground = True
        
        self.hurt_timer = 0
        self.combo_step = 0
        self.combo_buffered = False
        self.attack_pressed_last = False
        
        self.dash_timer = 0
        self.dash_cooldown = 0
        self.dash_dx = 0       # dash direction X (-1, 0, 1)
        self.dash_dy = 0       # dash direction Y (-1, 0, 1)
        self.dashing = False   # True while dash animation is playing
        self.arrow_spawned_this_frame = False
        self.double_shot_done = False

    def load_assets(self):
        w, h = 64, 64
        scale = 2.5
        folder = ARCHER_DIR
        
        idle = load_frames_from_folder(folder, 'IDLE', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
        run = load_frames_from_folder(folder, 'RUN', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
        attack = load_frames_from_folder(folder, 'ATTACK', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
        dash = load_frames_from_folder(folder, 'DASH', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
        hit = load_frames_from_folder(folder, 'HURT', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]
        death = load_frames_from_folder(folder, 'DEATH', scale=scale) or [pygame.Surface((int(w * scale), int(h * scale)))]

        frames = {
            'idle': idle,
            'run': run,
            'attack': attack,
            'dash': dash,
            'hit': hit,
            'death': death
        }
        durations = {
            'idle': 150,
            'run': 100,
            'attack': 60,
            'dash': 80,
            'hit': 100,
            'death': 100
        }
        loop_states = {'idle', 'run'}
        self.animator = Animator(frames, durations, default_state='idle', loop_states=loop_states)

    def take_damage(self, amount, source_x=None):
        if self.hp <= 0 or self.dashing:
            return  # i-frames during dash
            
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        else:
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            self.vel.x = -self.facing * 3
            self.hurt_timer = 300
            self.combo_step = 0
            self.combo_buffered = False

    def update(self, dt, keys=None, groups=None):
        if keys is None or groups is None:
            return

        if self.hp <= 0:
            if getattr(self, 'animator', None) is not None:
                self.animator.update(dt)
                mid = self.rect.midbottom
                frame = self.animator.get_frame()
                if self.facing == -1:
                    frame = pygame.transform.flip(frame, True, False)
                self.image = frame
                self.rect = self.image.get_rect(midbottom=mid)
            return

        if self.dash_cooldown > 0:
            self.dash_cooldown -= dt

        if self.dashing:
            self.animator.update(dt)
            # Only move during animation frames  (0-indexed 2-5)
            frame = self.animator.frame_index
            dash_speed = 6  # pixels per game-frame (easy to adjust)
            if 2 <= frame <= 5:
                self.rect.x += int(self.dash_dx * dash_speed)
                self.rect.y += int(self.dash_dy * dash_speed)
            if self.animator.is_finished():
                self.dashing = False
                self.vel.x = 0
                self.vel.y = 0
                self.animator.set_state('idle', reset=False)
        elif self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.8
            if self.hurt_timer <= 0:
                self.animator.set_state('idle', reset=False)
            self.animator.update(dt)
        else:
            self.handle_input(keys, groups)

            # If handle_input just started a dash, skip the rest.
            # the dashing block will take over on the next frame.
            if self.dashing:
                self.animator.update(dt)
            else:
                self.rect.x += int(self.vel.x)
                self.rect.y += int(self.vel.y)

                if self.animator.state == 'attack':
                    # Frame 9 arrow spawn
                    if self.animator.frame_index == 9 and not self.arrow_spawned_this_frame:
                        self.spawn_arrow(groups)
                        self.arrow_spawned_this_frame = True
                        
                        if self.combo_step == 3 and not self.double_shot_done:
                            self.animator.frame_index = 4
                            self.animator.time = 0
                            self.double_shot_done = True
                            self.arrow_spawned_this_frame = False

                    if self.animator.frame_index != 9:
                        self.arrow_spawned_this_frame = False

                    if self.animator.is_finished():
                        if self.combo_buffered:
                            self.combo_step += 1
                            self.combo_buffered = False
                            self.animator.set_state('attack', reset=True)
                            self.double_shot_done = False
                            self.arrow_spawned_this_frame = False
                        else:
                            self.combo_step = 0
                            self.animator.set_state('idle', reset=False)
                else:
                    if abs(self.vel.x) > 0 or abs(self.vel.y) > 0:
                        self.animator.set_state('run', reset=False)
                    else:
                        self.animator.set_state('idle', reset=False)

                self.animator.update(dt)

        # Update image
        mid = self.rect.midbottom
        frame = self.animator.get_frame()
        if self.facing == -1:
            frame = pygame.transform.flip(frame, True, False)
        self.image = frame
        self.rect = self.image.get_rect(midbottom=mid)

        # Clamp position
        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))

    def handle_input(self, keys, groups):
        self.vel.x = 0
        self.vel.y = 0

        attack_pressed = keys[pygame.K_j]
        just_pressed_attack = attack_pressed and not self.attack_pressed_last
        self.attack_pressed_last = attack_pressed

        is_attacking = self.animator.state == 'attack'

        if keys[pygame.K_k] and self.dash_cooldown <= 0 and not is_attacking:
            # Determine dash direction from current movement input
            self.dash_dx = 0
            self.dash_dy = 0
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.dash_dx = -1
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.dash_dx = 1
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                self.dash_dy = -1
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                self.dash_dy = 1

            # If no direction pressed, dash in the facing direction
            if self.dash_dx == 0 and self.dash_dy == 0:
                self.dash_dx = self.facing

            # Update facing based on horizontal dash direction
            if self.dash_dx != 0:
                self.facing = self.dash_dx

            self.animator.set_state('dash', reset=True)
            self.dashing = True
            self.dash_cooldown = 1500
            return

        if just_pressed_attack:
            if not is_attacking:
                self.combo_step = 1
                self.animator.set_state('attack', reset=True)
                self.double_shot_done = False
                self.arrow_spawned_this_frame = False
            else:
                if self.combo_step < 3:
                    self.combo_buffered = True

        if is_attacking:
            return

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vel.x = -self.speed
            self.facing = -1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vel.x = self.speed
            self.facing = 1
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.vel.y = -self.speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.vel.y = self.speed

    def spawn_arrow(self, groups):
        spawn_y = self.rect.bottom - 6 - self.rect.height // 2
        spawn_x = self.rect.centerx + (20 * self.facing)
        arrow = Arrow(spawn_x, spawn_y, self.facing, damage=20)
        groups['arrows'].add(arrow)

    def on_death(self):
        print('Archer died')
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
