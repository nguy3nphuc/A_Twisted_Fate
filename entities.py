import pygame
import time
import random
import math
from sprites import Animator, load_character_animations
from config import (MIN_Y, MAX_Y, MIN_X, MAX_X,
                     ENEMY_ATTACK_OFFSET_Y,
                     DEATH_FADE_DELAY, DEATH_FADE_DURATION, ARROW_IMAGE,
                     DAMAGE_FONT_PATH, CRIT_CHANCE, CRIT_MULTIPLIER,
                     DAMAGE_NUMBER_FONT_SIZE, DAMAGE_NUMBER_CRIT_FONT_SIZE,
                     DAMAGE_NUMBER_RISE_SPEED, DAMAGE_NUMBER_DURATION,
                     DAMAGE_NUMBER_COLOR, DAMAGE_NUMBER_CRIT_COLOR,
                     SPEAR_IMAGE,
                     GOBLIN_TANK_ATTACK_RANGE_X, GOBLIN_TANK_ATTACK_RANGE_Y,
                     GOBLIN_WARRIOR_ATTACK_RANGE_X, GOBLIN_WARRIOR_ATTACK_RANGE_Y,
                     GOBLIN_SPEARMAN_ATTACK_RANGE_X, GOBLIN_SPEARMAN_ATTACK_RANGE_Y,
                     GOBLIN_TANK_ATTACK_2_RANGE_X, GOBLIN_TANK_ATTACK_2_RANGE_Y,
                     DASH_SMOKE_IMAGE, ULTIMATE_EFFECT_IMAGE,
                     ARCHER_ULTIMATE_DAMAGE, ARCHER_ULTIMATE_SPEED,
                     ARCHER_ULTIMATE_COOLDOWN, ARCHER_ULTIMATE_CAST_FRAME,
                     KNIGHT_ULTIMATE_DAMAGE, KNIGHT_ULTIMATE_KNOCKBACK,
                     KNIGHT_ULTIMATE_COOLDOWN, KNIGHT_ULTIMATE_CAST_FRAME,
                     LIZARDMAN_ATTACK_RANGE_X, LIZARDMAN_ATTACK_RANGE_Y,
                     CYCLOP_ATTACK_RANGE_X, CYCLOP_ATTACK_RANGE_Y,
                     CYCLOP_SPECIAL_COOLDOWN,
                     KOBOLD_ATTACK_RANGE_X, KOBOLD_ATTACK_RANGE_Y,
                     KOBOLD_DASH_RANGE_X, KOBOLD_DASH_RANGE_Y,
                     KOBOLD_DASH_COOLDOWN,
                     FIREWORM_ATTACK_RANGE, FIREBALL_SPEED,
                     FAT_CULTIST_ATTACK_RANGE_X, FAT_CULTIST_ATTACK_RANGE_Y,
                     FAT_CULTIST_ATTACK_2_RANGE_X, FAT_CULTIST_ATTACK_2_RANGE_Y,
                     DEATH_BRINGER_ATTACK_RANGE_X, DEATH_BRINGER_ATTACK_RANGE_Y,
                     DEATH_BRINGER_CAST_RANGE_X, DEATH_BRINGER_CAST_RANGE_Y,
                     DEATH_BRINGER_SPELL_COOLDOWN,
                     RESOURCE_DEFAULT_ARMOR_RATIO, RESOURCE_DEFAULT_MANA_RATIO,
                     RESOURCE_MAX_ARMOR_CAP, RESOURCE_MAX_MANA_CAP,
                     DEFAULT_ARMOR_REDUCTION_PCT,
                     PLAYER_RESOURCE_PRESETS, ARCHER_ARROW_CONFIG)


def _hurtbox_from_config(anim_config, default_w=40, default_h=80, default_ox=0):
    """Extract hurtbox dimensions from the metadata-driven animation config.

    ``load_character_animations`` stamps ``hurtbox_w``, ``hurtbox_h``, and
    ``hurtbox_offset_x`` onto every animation entry from the character-level
    metadata.  We read them from the first available state here so entities
    don't need to hard-code these values.
    """
    for entry in anim_config.values():
        if isinstance(entry, dict) and 'hurtbox_w' in entry:
            return (entry['hurtbox_w'],
                    entry['hurtbox_h'],
                    entry.get('hurtbox_offset_x', default_ox))
    return (default_w, default_h, default_ox)


class HealthMixin:
    def __init__(self, max_hp, max_armor=None, max_mana=None, armor_reduction_pct=0.25):
        self.max_hp = max_hp
        self.hp = max_hp

        # Shared resource fields for all entities (players + enemies).
        if max_armor is None:
            max_armor = max(0, min(RESOURCE_MAX_ARMOR_CAP, int(max_hp * RESOURCE_DEFAULT_ARMOR_RATIO)))
        if max_mana is None:
            max_mana = max(0, min(RESOURCE_MAX_MANA_CAP, int(max_hp * RESOURCE_DEFAULT_MANA_RATIO)))

        self.max_armor = int(max_armor)
        self.armor = float(self.max_armor)
        self.armor_reduction_pct = max(0.0, min(0.9, float(armor_reduction_pct if armor_reduction_pct is not None else DEFAULT_ARMOR_REDUCTION_PCT)))
        self.max_mana = int(max_mana)
        self.mana = float(self.max_mana)

        # EnemyHealthBar is defined later in this module but is always available
        # at runtime when enemy instances are created.
        self.health_bar = EnemyHealthBar(max_hp)

    def _ensure_health_bar(self):
        """No-op kept for compatibility; bar is now created in __init__."""
        pass

    def take_damage(self, amount, source_x=None, is_crit=False):
        # ignore damage if already dead
        if self.hp <= 0:
            return
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        # Notify the health bar about the new HP so catchup resets properly.
        # We call this even on death so the bar reflects 0 before fade-out.
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def on_death(self):
        self.kill()

    def _get_true_pivot(self):
        """Returns the true visual pivot point (x, y) of the character on screen."""
        if not hasattr(self, 'rect'):
            return (0, 0)
        foot_x = self.rect.midbottom[0] - getattr(self, 'current_pdx', 0)
        foot_y = self.rect.midbottom[1] - getattr(self, 'current_pdy', 0)
        
        animator = getattr(self, 'animator', None)
        if not animator:
            return (foot_x, foot_y)
            
        sn = getattr(animator, 'state', None)
        entry = getattr(animator, 'states_config', {}).get(sn, {})
        idle_mb_ox = entry.get('idle_mb_ox', 0)
        idle_mb_oy = entry.get('idle_mb_oy', 0)
        
        if getattr(self, 'facing', 1) == 1:
            return foot_x + idle_mb_ox, foot_y + idle_mb_oy
        else:
            return foot_x - idle_mb_ox, foot_y + idle_mb_oy


# ── Asset path helper ──────────────────────────────────────────────────────────
import os as _os
_HEALTH_BAR_DIR = _os.path.join(_os.path.dirname(__file__), 'assets', 'monster_health_bar')


class EnemyHealthBar:
    """Sprite-based health bar with a smooth delayed catch-up animation.

    Layer order (bottom → top):
        1. no_health.png  – empty bar background
        2. health_catchup.png  – orange catch-up indicator
        3. health.png  – actual current HP (red)

    Usage::

        # In enemy update():
        if self.health_bar:
            self.health_bar.update(dt)

        # In the draw loop:
        if enemy.health_bar:
            enemy.health_bar.draw(surface, enemy, camera_offset)
    """

    # Vertical distance above the hurtbox top where the bar is centred.
    VERTICAL_OFFSET = 30  # pixels above hurtbox.top

    # How long (ms) after a hit before the catch-up bar starts shrinking.
    CATCHUP_DELAY = 200  # ms

    # Speed at which catchup_ratio moves toward current_ratio each ms.
    # Expressed as a fraction per ms (e.g. 0.004 = 0.4 % per ms).
    CATCHUP_SPEED = 0.004  # ratio/ms  → full drain in ~250 ms

    def __init__(self, max_hp: int):
        self.max_hp = max_hp
        self.current_hp: float = float(max_hp)

        # Displayed ratios  (0.0 – 1.0)
        self.display_ratio: float = 1.0   # health bar width
        self.catchup_ratio: float = 1.0   # catch-up bar width

        # Catch-up delay countdown (counts down from CATCHUP_DELAY to 0 in ms)
        self.catchup_timer: float = 0.0

        # Load and cache images (class-level cache to avoid re-loading per enemy)
        self._bg, self._catchup, self._health = self._load_images()

        # Natural width of the bar sprites (they should all be identical)
        self._bar_width: int = self._bg.get_width()
        self._bar_height: int = self._bg.get_height()

    # ── Class-level image cache ────────────────────────────────────────────────

    _image_cache: dict = {}

    @classmethod
    def _load_images(cls):
        if cls._image_cache:
            return cls._image_cache['bg'], cls._image_cache['catchup'], cls._image_cache['health']

        def _load(name):
            path = _os.path.join(_HEALTH_BAR_DIR, name)
            try:
                return pygame.image.load(path).convert_alpha()
            except Exception:
                # Fallback 1px solid colour strip if asset is missing
                surf = pygame.Surface((80, 8), pygame.SRCALPHA)
                colour = {'health.png': (200, 0, 0),
                          'health_catchup.png': (230, 140, 0),
                          'no_health.png': (40, 40, 40)}.get(name, (80, 80, 80))
                surf.fill(colour)
                return surf

        cls._image_cache['bg']      = _load('no_health.png')
        cls._image_cache['catchup'] = _load('health_catchup.png')
        cls._image_cache['health']  = _load('health.png')
        return cls._image_cache['bg'], cls._image_cache['catchup'], cls._image_cache['health']

    # ── Public API ─────────────────────────────────────────────────────────────

    def notify_damage(self, new_hp: float):
        """Called immediately when the enemy's HP changes.

        Updates display_ratio instantly; resets the catch-up delay so the
        orange bar holds for CATCHUP_DELAY ms before chasing.
        The catch-up bar's *current visual position* is never snapped —
        it continues smoothly from wherever it currently is.
        """
        self.current_hp = max(0.0, float(new_hp))
        self.display_ratio = self.current_hp / self.max_hp if self.max_hp > 0 else 0.0
        # Reset delay so the player sees the orange segment for a moment.
        self.catchup_timer = self.CATCHUP_DELAY

    def update(self, dt: float):
        """Advance catch-up animation.  Call every frame with dt in ms."""
        if self.catchup_timer > 0:
            self.catchup_timer -= dt
            return  # hold — do not shrink yet

        # Once the delay expires, lerp catchup_ratio toward display_ratio.
        target = self.display_ratio
        if self.catchup_ratio > target:
            step = self.CATCHUP_SPEED * dt
            self.catchup_ratio = max(target, self.catchup_ratio - step)
        else:
            self.catchup_ratio = target  # snap if somehow overshot

    def draw(self, surface: pygame.Surface, enemy, camera_offset=(0, 0)):
        """Render the three-layer health bar above the enemy.

        Anchored to enemy.hurtbox.  Falls back to enemy.rect if no hurtbox.
        """
        hurtbox = getattr(enemy, 'hurtbox', enemy.rect)
        ox, oy = camera_offset

        bar_x = hurtbox.centerx - self._bar_width // 2 + ox
        bar_y = hurtbox.top - self.VERTICAL_OFFSET + oy

        # 1. Background (full width, always)
        surface.blit(self._bg, (bar_x, bar_y))

        # 2. Catch-up bar (cropped to catchup_ratio)
        catchup_w = int(self._bar_width * max(0.0, self.catchup_ratio))
        if catchup_w > 0:
            src_rect = pygame.Rect(0, 0, catchup_w, self._bar_height)
            surface.blit(self._catchup, (bar_x, bar_y), src_rect)

        # 3. Current HP bar (cropped to display_ratio)
        health_w = int(self._bar_width * max(0.0, self.display_ratio))
        if health_w > 0:
            src_rect = pygame.Rect(0, 0, health_w, self._bar_height)
            surface.blit(self._health, (bar_x, bar_y), src_rect)


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
        self.already_hit_targets = set()

    def update(self, dt):
        if pygame.time.get_ticks() - self.spawn_time > self.duration:
            self.kill()


class DamageNumber(pygame.sprite.Sprite):
    """Floating damage number that pops up when an enemy takes damage.
    Normal hits: red, standard size.
    Critical hits: red, larger font with a brief scale-up pop effect.
    """
    _font_cache = {}  # class-level cache so the font is only loaded once per size

    @classmethod
    def _get_font(cls, size):
        if size not in cls._font_cache:
            try:
                cls._font_cache[size] = pygame.font.Font(DAMAGE_FONT_PATH, size)
            except Exception:
                cls._font_cache[size] = pygame.font.SysFont('Arial', size, bold=True)
        return cls._font_cache[size]

    def __init__(self, x, y, damage, is_crit=False):
        super().__init__()
        self.is_crit = is_crit
        self.elapsed = 0
        self.duration = DAMAGE_NUMBER_DURATION
        self.rise_speed = DAMAGE_NUMBER_RISE_SPEED
        self.float_x = float(x + random.randint(-10, 10))
        self.float_y = float(y - 20)

        # Choose font size and text
        if is_crit:
            font_size = DAMAGE_NUMBER_CRIT_FONT_SIZE
            self.text = str(damage) + "!"
            top_color = (180, 0, 0)
            bottom_color = (255, 80, 80)
        else:
            font_size = DAMAGE_NUMBER_FONT_SIZE
            self.text = str(damage)
            top_color = (130, 0, 0)
            bottom_color = (255, 120, 120)

        self.font = self._get_font(font_size)
        
        # Pre-render the decorated text surface
        text_mask = self.font.render(self.text, True, (255, 255, 255))
        w, h = text_mask.get_size()
        
        # Gradient
        grad_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for yy in range(h):
            ratio = yy / max(1, h - 1)
            r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
            g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
            b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
            pygame.draw.line(grad_surf, (r, g, b, 255), (0, yy), (w, yy))
        
        # Multiply gradient by the text's alpha mask
        grad_surf.blit(text_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        
        # Shadow
        shadow_offset = 1

        shadow = self.font.render(self.text, True, (30, 30, 30))
        shadow.set_alpha(120)

        self.base_image = pygame.Surface(
            (w + shadow_offset, h + shadow_offset),
            pygame.SRCALPHA
        )

        # Shadow phía dưới bên phải
        self.base_image.blit(shadow, (shadow_offset, shadow_offset))

        # Text chính
        self.base_image.blit(grad_surf, (0, 0))

        # Pop scale animation for crits: starts bigger, shrinks to 1.0
        self.scale = 1.6 if is_crit else 1.0
        self.target_scale = 1.0

        self._render()

    def _render(self):
        """Render the text surface with current scale and alpha."""
        base = self.base_image
        if self.scale != 1.0:
            w = max(1, int(base.get_width() * self.scale))
            h = max(1, int(base.get_height() * self.scale))
            base = pygame.transform.scale(base, (w, h))

        # Apply fade-out and shrink animation
        progress = self.elapsed / self.duration
        # Start fading at 50% of duration
        if progress > 0.5:
            fade_progress = (progress - 0.5) / 0.5
            alpha = max(0, int(255 * (1.0 - fade_progress)))
            self.scale = max(0.1, self.target_scale * (1.0 - fade_progress * 0.8))
        else:
            alpha = 255

        if alpha < 255:
            base = base.copy()
            base.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)

        self.image = base
        self.rect = self.image.get_rect(center=(int(self.float_x), int(self.float_y)))

    def update(self, dt):
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.kill()
            return

        # Float upward initially, but float down when phasing out
        progress = self.elapsed / self.duration
        if progress > 0.5:
            self.float_y += self.rise_speed * 1.5
        else:
            self.float_y -= self.rise_speed

        # Ease scale back to 1.0 for crit pop effect
        if self.scale > self.target_scale:
            self.scale = max(self.target_scale, self.scale - 0.04)

        self._render()


class KnightUltimateShockwave(pygame.sprite.Sprite):
    """A massive ground shockwave spawned at the peak of the Knight's ultimate.

    The shockwave covers a wide area in the knight's facing direction and deals
    KNIGHT_ULTIMATE_DAMAGE.  Every enemy struck receives an enormous knockback
    (KNIGHT_ULTIMATE_KNOCKBACK) so they are blasted far across the screen.
    The hitbox lives for 250 ms — long enough to catch enemies stepping into it.

    Collision tracking (already_hit_targets) ensures each enemy is damaged only
    once per shockwave.  The game.py loop uses the 'knight_shockwaves' group to
    drive collision resolution.
    """

    DURATION = 250   # ms the hitbox stays alive

    def __init__(self, owner_hurtbox, facing, damage, knockback):
        super().__init__()
        self.damage   = damage
        self.knockback = knockback
        self.facing   = facing
        self.spawn_time = pygame.time.get_ticks()
        self.already_hit_targets: set = set()

        # Massive oval range around the knight (flat on the ground)
        w = 500
        h = 180

        # Place the shockwave centered on the knight's feet
        hb_x = owner_hurtbox.centerx - w // 2
        hb_y = owner_hurtbox.bottom - h // 2

        self.rect = pygame.Rect(hb_x, hb_y, w, h)

        # Visual: a translucent golden-white flash
        self.image = pygame.Surface((w, h), pygame.SRCALPHA)
        # Draw a radial-style glow — bright centre, fades to edges
        centre_color  = (255, 240, 120, 200)
        edge_color    = (255, 160,  40,   0)
        mid_x, mid_y  = w // 2, h // 2
        
        # Draw concentric ellipses fading outward
        steps = 50
        for i in range(steps, 0, -1):
            t = i / steps
            alpha = int(edge_color[3] + (centre_color[3] - edge_color[3]) * (1 - t))
            cr = int(edge_color[0] + (centre_color[0] - edge_color[0]) * (1 - t))
            cg = int(edge_color[1] + (centre_color[1] - edge_color[1]) * (1 - t))
            cb = int(edge_color[2] + (centre_color[2] - edge_color[2]) * (1 - t))
            
            ew = int(w * t)
            eh = int(h * t)
            if ew <= 0 or eh <= 0:
                continue
                
            ex = mid_x - ew // 2
            ey = mid_y - eh // 2
            
            pygame.draw.ellipse(self.image, (cr, cg, cb, alpha), (ex, ey, ew, eh))
            
        # Draw a sharp, visible boundary outline so the player can clearly see the oval edge
        pygame.draw.ellipse(self.image, (255, 200, 50, 180), (0, 0, w, h), max(3, w//150))

    @property
    def floor_y(self):
        return self.rect.centery

    def can_hit(self, enemy):
        return id(enemy) not in self.already_hit_targets

    def collides_with(self, enemy):
        """Check if enemy's hurtbox center is within the shockwave's ellipse."""
        # Check bounding rect first for efficiency
        if not self.rect.colliderect(enemy.hurtbox):
            return False
            
        cx, cy = self.rect.center
        a = self.rect.width / 2
        b = self.rect.height / 2
        
        if a <= 0 or b <= 0:
            return False
            
        ex, ey = enemy.hurtbox.center
        dx = ex - cx
        dy = ey - cy
        
        return (dx * dx) / (a * a) + (dy * dy) / (b * b) <= 1.0

    def register_hit(self, enemy):
        self.already_hit_targets.add(id(enemy))

    def update(self, dt):
        elapsed = pygame.time.get_ticks() - self.spawn_time
        # Fade out the visual as the hitbox expires
        ratio = max(0.0, 1.0 - elapsed / self.DURATION)
        alpha = int(255 * ratio)
        self.image.set_alpha(alpha)
        if elapsed >= self.DURATION:
            self.kill()


class Knight(pygame.sprite.Sprite, HealthMixin):
    def __init__(self, pos=(200, 300)):
        pygame.sprite.Sprite.__init__(self)
        _preset = PLAYER_RESOURCE_PRESETS.get('knight', {})
        HealthMixin.__init__(
            self,
            max_hp=1000000000,
            max_armor=_preset.get('max_armor', 70),
            max_mana=_preset.get('max_mana', 100),
            armor_reduction_pct=_preset.get('armor_reduction_pct', 0.40),
        )
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.vel = pygame.math.Vector2(0, 0)
        self.speed = 4
        self.facing = 1
        self.on_ground = True
        self.controls = {
            'left': [pygame.K_a],
            'right': [pygame.K_d],
            'up': [pygame.K_w],
            'down': [pygame.K_s],
            'attack': [pygame.K_j, pygame.K_u],
            'defend': [pygame.K_k, pygame.K_i],
            'ultimate': [pygame.K_l, pygame.K_o],
        }
        self.attack_cooldown = 0
        self.hurt_timer = 0
        self.combo_step = 0
        self.combo_buffered = False
        self.exceeded_combo = False
        self.combo_break_timer = 0
        self.attack_pressed_last = False
        self.has_attacked = False # flag to ensure damage is dealt only once at midpoint
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config,
            default_w=50, default_h=85, default_ox=20)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox

        # -- Ultimate --
        self.ultimate_cooldown = 0
        self.ultimate_pressed_last = False
        self._ultimate_shockwave_spawned = False
        
        # -- Skills Inventory --
        self.skills = []  # List of skill types that have been picked up
        self.active_skill = None  # Currently selected skill (if any)
        self.target_skill_idx = 0  # Selected skill slot index (0..2)

    @property
    def foot_y(self):
        """Ground-plane Y position of this character (pivot-corrected foot)."""
        return self.hurtbox.bottom

    def _is_control_pressed(self, control_name, keys):
        for key in self.controls.get(control_name, []):
            if keys[key]:
                return True
        return False

    def load_assets(self):
        anim_config = load_character_animations('knight')

        # --- Split run into start (frame 0) and loop (frames 1-N) ---
        # Frame 0 is the start-run pose; it plays once then hands off to
        # run_loop which loops frames 1-N continuously.
        if 'run' in anim_config:
            run_info = anim_config.pop('run')
            run_frames = run_info['frames']
            run_dur = run_info.get('duration', 100)
            if len(run_frames) > 1:
                anim_config['run_start'] = {
                    'frames': run_frames[:1], 'duration': run_dur, 'loop': False
                }
                anim_config['run_loop'] = {
                    'frames': run_frames[1:], 'duration': run_dur, 'loop': True
                }
            else:
                anim_config['run_start'] = {
                    'frames': run_frames, 'duration': run_dur, 'loop': True
                }
                anim_config['run_loop'] = {
                    'frames': run_frames, 'duration': run_dur, 'loop': True
                }

        # --- Split defend (11 frames) into four sub-states ---
        # Layout:
        #   Frames  0-4  (5 frames) : startup / enter-defend sequence
        #   Frame   4    (hold)     : defend_idle holds on this frame
        #   Frames  5-8  (4 frames) : block-impact reaction
        #   Frames  9-10 (2 frames) : return to idle
        if 'defend' in anim_config:
            defend_info = anim_config.pop('defend')
            defend_frames = defend_info['frames']
            defend_dur = defend_info.get('duration', 120)
            n = len(defend_frames)
            # defend_start  — frames 0..4  (5 startup frames)
            start_end = min(5, n)
            anim_config['defend_start'] = {
                'frames': defend_frames[:start_end], 'duration': defend_dur, 'loop': False
            }
            # defend_idle   — frame 4 only, loops as a 1-frame hold
            hold_idx = min(4, n - 1)
            anim_config['defend_idle'] = {
                'frames': [defend_frames[hold_idx]], 'duration': defend_dur, 'loop': True
            }
            # defend_hit    — frames 5..8  (4 block-impact frames)
            hit_start = min(5, n)
            hit_end   = min(9, n)
            anim_config['defend_hit'] = {
                'frames': defend_frames[hit_start:hit_end] if hit_start < n else [defend_frames[hold_idx]],
                'duration': 80, 'loop': False
            }
            # defend_return — frames 9..10  (2 return frames)
            ret_start = min(9, n)
            anim_config['defend_return'] = {
                'frames': defend_frames[ret_start:] if ret_start < n else [defend_frames[-1]],
                'duration': defend_dur, 'loop': False
            }

        self.animator = Animator.from_config(anim_config)

    def _apply_frame(self):
        """Apply current animation frame with pivot alignment correction."""
        pdx_old = getattr(self, 'current_pdx', 0)
        pdy_old = getattr(self, 'current_pdy', 0)
        self.rect.x -= pdx_old
        self.rect.y -= pdy_old

        mid = self.rect.midbottom
        frame = self.animator.get_frame()
        pdx, pdy = self.animator.get_pivot_delta()
        if self.facing == -1:
            frame = pygame.transform.flip(frame, True, False)
            pdx = -pdx
        self.image = frame
        self.rect = self.image.get_rect(midbottom=mid)
        self.rect.x += pdx
        self.rect.y += pdy
        self.current_pdx = pdx
        self.current_pdy = pdy
        self._update_hurtbox()

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0:
            return

        # Invincible during the ultimate slam animation
        if getattr(self, 'animator', None) is not None and self.animator.state == 'ultimate':
            return
            
        # Block is active during the entire defend sequence.
        is_defending = getattr(self, 'animator', None) is not None and self.animator.state in ('defend_start', 'defend_idle', 'defend_hit')
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
                self._apply_frame()
            return

        # handle timers
        if self.combo_break_timer > 0:
            self.combo_break_timer -= dt

        if self.ultimate_cooldown > 0:
            self.ultimate_cooldown -= dt

        # ULTIMATE block — Knight is locked in the 44-frame slam animation
        if getattr(self, 'animator', None) is not None and self.animator.state == 'ultimate':
            fi = self.animator.frame_index
            # Spawn the shockwave at the designated cast frame
            if fi >= KNIGHT_ULTIMATE_CAST_FRAME and not self._ultimate_shockwave_spawned:
                self._spawn_ultimate_shockwave(groups)
                self._ultimate_shockwave_spawned = True
            if self.animator.is_finished():
                self.animator.set_state('idle', reset=False)
            self.animator.update(dt)
            self._apply_frame()
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            # Clamp by the logical foot (hurtbox.bottom) not rect.bottom.
            # rect.bottom includes the raw pivot offset pdy, which can push it
            # well beyond MAX_Y for tall animation canvases — clamping rect.bottom
            # directly would pull the whole sprite up.
            clamped_foot = max(MIN_Y, min(MAX_Y, self.hurtbox.bottom))
            foot_shift = clamped_foot - self.hurtbox.bottom
            if foot_shift != 0:
                self.rect.y += foot_shift
                self.hurtbox.y += foot_shift
            return

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
                    self._apply_frame()
                return

        self.handle_input(keys, groups)

        # Yield immediately if handle_input started the ultimate
        if getattr(self, 'animator', None) is not None and self.animator.state == 'ultimate':
            self.animator.update(dt)
            self._apply_frame()
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            clamped_foot = max(MIN_Y, min(MAX_Y, self.hurtbox.bottom))
            foot_shift = clamped_foot - self.hurtbox.bottom
            if foot_shift != 0:
                self.rect.y += foot_shift
                self.hurtbox.y += foot_shift
            return
        
        self.rect.x += int(self.vel.x)
        self.rect.y += int(self.vel.y)

        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt

        # choose animation state
        if getattr(self, 'animator', None) is not None:
            if self.animator.state in ('attack1', 'attack2', 'attack3'):
                # Check for the designated hit frame to spawn hitbox
                if self.animator.is_at_hit_frame() and not self.has_attacked:
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

            # --- Run start (frame 0, plays once) → loop transition ---
            # Bug fix: run_start has only 1 frame so Animator.update() returns
            # early without ever setting finished=True. Check len<=1 as well.
            elif self.animator.state == 'run_start':
                run_start_frames = self.animator.states.get('run_start', [])
                if self._is_control_pressed('defend', keys):
                    # Defend can always interrupt the start frame
                    self.animator.set_state('defend_start', reset=True)
                    self.vel.x = 0
                    self.vel.y = 0
                elif self.animator.is_finished() or len(run_start_frames) <= 1:
                    # 1-frame start: transition immediately on the next tick
                    if abs(self.vel.x) > 0 or abs(self.vel.y) > 0:
                        self.animator.set_state('run_loop', reset=True)
                    else:
                        self.animator.set_state('idle', reset=False)

            # --- Run loop (frames 1-N, loops) ---
            elif self.animator.state == 'run_loop':
                if self._is_control_pressed('defend', keys):
                    self.animator.set_state('defend_start', reset=True)
                    self.vel.x = 0
                    self.vel.y = 0
                elif not (abs(self.vel.x) > 0 or abs(self.vel.y) > 0):
                    self.animator.set_state('idle', reset=False)

            # --- Defend sub-state machine ---
            elif self.animator.state == 'defend_start':
                # Play startup; then hold in defend_idle while key held
                if self.animator.is_finished():
                    if self._is_control_pressed('defend', keys):
                        self.animator.set_state('defend_idle', reset=True)
                    else:
                        self.animator.set_state('defend_return', reset=True)

            elif self.animator.state == 'defend_idle':
                # Loop the hold frame; break out when key released
                if not self._is_control_pressed('defend', keys):
                    self.animator.set_state('defend_return', reset=True)

            elif self.animator.state == 'defend_hit':
                if self.animator.is_finished():
                    if self._is_control_pressed('defend', keys):
                        self.animator.set_state('defend_idle', reset=True)
                    else:
                        self.animator.set_state('defend_return', reset=True)

            elif self.animator.state == 'defend_return':
                if self.animator.is_finished():
                    self.animator.set_state('idle', reset=False)

            else:
                # Idle / any other state
                if self._is_control_pressed('defend', keys):
                    self.animator.set_state('defend_start', reset=True)
                    self.vel.x = 0
                    self.vel.y = 0
                elif abs(self.vel.x) > 0 or abs(self.vel.y) > 0:
                    self.animator.set_state('run_start', reset=True)
                else:
                    self.animator.set_state('idle', reset=False)
            self.animator.update(dt)
            self._apply_frame()

        # Clamp position AFTER animation rect update so bounds are always enforced.
        # Clamp the logical foot (hurtbox.bottom) not rect.bottom — rect.bottom
        # includes the pivot offset pdy and clamping it directly would shift the
        # sprite up when the character stands near the bottom boundary.
        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        clamped_foot = max(MIN_Y, min(MAX_Y, self.hurtbox.bottom))
        foot_shift = clamped_foot - self.hurtbox.bottom
        if foot_shift != 0:
            self.rect.y += foot_shift
            self.hurtbox.y += foot_shift

    def handle_input(self, keys, groups):
        self.vel.x = 0
        self.vel.y = 0
        
        attack_pressed   = self._is_control_pressed('attack', keys)
        ultimate_pressed = self._is_control_pressed('ultimate', keys)
        just_pressed_attack   = attack_pressed   and not getattr(self, 'attack_pressed_last', False)
        just_pressed_ultimate = ultimate_pressed and not getattr(self, 'ultimate_pressed_last', False)
        self.attack_pressed_last   = attack_pressed
        self.ultimate_pressed_last = ultimate_pressed

        is_attacking = self.animator.state in ('attack1', 'attack2', 'attack3')
        is_defending = getattr(self, 'animator', None) is not None and self.animator.state in ('defend_start', 'defend_idle', 'defend_hit', 'defend_return')

        # Ultimate (L) — highest offensive priority
        if just_pressed_ultimate and self.ultimate_cooldown <= 0 and not is_attacking and not is_defending:
            self.animator.set_state('ultimate', reset=True)
            self.ultimate_cooldown = KNIGHT_ULTIMATE_COOLDOWN
            self._ultimate_shockwave_spawned = False
            self.combo_step = 0
            self.combo_buffered = False
            self.vel.x = 0
            self.vel.y = 0
            return

        if just_pressed_attack and self.combo_break_timer <= 0:
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

        if self._is_control_pressed('defend', keys):
            return

        if self._is_control_pressed('left', keys):
            self.vel.x = -self.speed
            self.facing = -1
        if self._is_control_pressed('right', keys):
            self.vel.x = self.speed
            self.facing = 1
        if self._is_control_pressed('up', keys):
            self.vel.y = -self.speed
        if self._is_control_pressed('down', keys):
            self.vel.y = self.speed

    def start_combo_step(self, step, groups):
        self.combo_step = step
        self.combo_buffered = False
        self.has_attacked = False
        
        state_name = f'attack{step}'
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state(state_name, reset=True)

    def spawn_attack_hitbox(self, groups):
        """Spawn a melee attack hitbox, reading size/offset from animation metadata."""
        step = self.combo_step
        damage = 15 + step * 5
        state_name = f'attack{step}'
        # Read hitbox dimensions from the metadata-driven config (fall back to
        # the old config.py values so nothing breaks if metadata is missing).
        anim_entry = self.animator.states_config.get(state_name, {}) \
            if hasattr(self.animator, 'states_config') else {}
        w        = anim_entry.get('hitbox_w',        150)
        h        = anim_entry.get('hitbox_h',         20)
        offset_x = anim_entry.get('hitbox_offset_x', -35)
        offset_y = anim_entry.get('hitbox_offset_y',  -5)

        pivot_x, pivot_y = self._get_true_pivot()

        if self.facing == 1:
            hb_x = pivot_x + offset_x
        else:
            hb_x = pivot_x - offset_x - w
        hb_y = pivot_y - h // 2 + offset_y

        hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=damage, duration=100)
        groups['attacks'].add(hitbox)

    def _spawn_ultimate_shockwave(self, groups):
        """Spawn the ground shockwave hitbox at the peak of the slam animation."""
        shockwave = KnightUltimateShockwave(
            owner_hurtbox=self.hurtbox,
            facing=self.facing,
            damage=KNIGHT_ULTIMATE_DAMAGE,
            knockback=KNIGHT_ULTIMATE_KNOCKBACK,
        )
        if 'effects' in groups:
            groups['effects'].add(shockwave)
        if 'knight_shockwaves' in groups:
            groups['knight_shockwaves'].add(shockwave)

    def on_death(self):
        print('Player died')
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0



# ── Phase 1 New Monster: Lizardman ────────────────────────────────────────────

class Lizardman(pygame.sprite.Sprite, HealthMixin):
    """Standard 2-hit melee combo enemy. Same pattern as GoblinWarrior."""

    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=50)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.speed = 1.3
        self.facing = -1
        self.attack_timer = 0
        self.vel = pygame.math.Vector2(0, 0)
        self.hurt_timer = 0
        self.ai_state = 'chase'
        self.ai_timer = 0
        self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
        self.has_attacked = False
        self.combo_step = 0
        self.dying = False
        self.death_fade_timer = 0
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=32, default_h=90, default_ox=0)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox

    @property
    def foot_y(self):
        return self.hurtbox.bottom

    def load_assets(self):
        anim_config = load_character_animations('lizardman')
        self.animator = Animator.from_config(anim_config)

    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0:
            return
        self._ensure_health_bar()
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        else:
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            knockback_dir = 1 if (source_x is not None and self.rect.centerx > source_x) else -1
            self.vel.x = knockback_dir * 1.8
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration
            self.combo_step = 0
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        if self.hp <= 0 or self.animator.state == 'death':
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)
            if not self.dying:
                self.update_animation(dt)
                if self.animator.is_finished():
                    self.dying = True
                    self.death_fade_timer = 0
            else:
                self.death_fade_timer += dt
                if self.death_fade_timer > self.death_fade_delay:
                    fade_progress = (self.death_fade_timer - self.death_fade_delay) / self.death_fade_duration
                    self.alpha = max(0, int(255 * (1.0 - fade_progress)))
                    self._apply_alpha()
                    if self.alpha <= 0:
                        self.kill()
            return

        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.8
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
            if self.hurt_timer <= 0:
                self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        current_attack = self.animator.state
        if current_attack in ('attack1', 'attack2'):
            if self.animator.is_at_hit_frame() and not self.has_attacked:
                damage = {1: 8, 2: 12}.get(self.combo_step, 8)
                self._spawn_enemy_attack_hitbox(groups, damage)
                self.has_attacked = True
            self.update_animation(dt)
            if self.animator.is_finished():
                dist_x = player.hurtbox.centerx - self.hurtbox.centerx
                dist_y = player.hurtbox.bottom - self.hurtbox.bottom
                in_range = abs(dist_x) <= LIZARDMAN_ATTACK_RANGE_X and abs(dist_y) <= LIZARDMAN_ATTACK_RANGE_Y
                if in_range and self.combo_step < 2:
                    self.combo_step += 1
                    self.animator.set_state(f'attack{self.combo_step}', reset=True)
                    self.has_attacked = False
                else:
                    self.combo_step = 0
                    self.animator.set_state('idle', reset=False)
                    self.ai_state = 'wait'
                    self.ai_timer = random.randint(500, 1000)
            return

        self.ai_timer -= dt

        if self.ai_state == 'wait':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
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

        moving = False
        self.vel.x = 0
        self.vel.y = 0
        if player is not None and player.hp > 0:
            target_x = player.rect.centerx + self.target_offset.x
            target_y = player.rect.bottom + self.target_offset.y
            dist_x = target_x - self.rect.centerx
            dist_y = target_y - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)
            real_dist_x = player.rect.centerx - self.rect.centerx
            real_dist_y = player.rect.bottom - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)

            if abs(real_dist_x) > LIZARDMAN_ATTACK_RANGE_X or abs(real_dist_y) > LIZARDMAN_ATTACK_RANGE_Y:
                if abs(dist_x) > 5:
                    if dist_x < 0:
                        self.rect.x -= self.speed
                        self.facing = -1
                    else:
                        self.rect.x += self.speed
                        self.facing = 1
                    moving = True
                if abs(dist_y) > 5:
                    self.rect.y += self.speed if dist_y > 0 else -self.speed
                    moving = True
                if random.random() < 0.005:
                    self.ai_state = 'idle'
                    self.ai_timer = random.randint(1000, 2000)
            else:
                if pygame.time.get_ticks() - self.attack_timer > 1500:
                    self.combo_step = 1
                    self.animator.set_state('attack1', reset=True)
                    self.has_attacked = False
                    self.attack_timer = pygame.time.get_ticks()

        if moving:
            self.animator.set_state('run', reset=False)
        else:
            if self.animator.state not in ('attack1', 'attack2', 'hit', 'death'):
                self.animator.set_state('idle', reset=False)

        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
        self.update_animation(dt)

    def update_animation(self, dt):
        if getattr(self, 'animator', None) is not None:
            self.animator.update(dt)
            pdx_old = getattr(self, 'current_pdx', 0)
            pdy_old = getattr(self, 'current_pdy', 0)
            self.rect.x -= pdx_old
            self.rect.y -= pdy_old
            mid = self.rect.midbottom
            frame = self.animator.get_frame()
            pdx, pdy = self.animator.get_pivot_delta()
            if self.facing == -1:
                frame = pygame.transform.flip(frame, True, False)
                pdx = -pdx
            self.image = frame
            self.rect = self.image.get_rect(midbottom=mid)
            self.rect.x += pdx
            self.rect.y += pdy
            self.current_pdx = pdx
            self.current_pdy = pdy
            self._update_hurtbox()

    def _apply_alpha(self):
        if self.image is not None:
            faded = self.image.copy()
            faded.fill((255, 255, 255, self.alpha), special_flags=pygame.BLEND_RGBA_MULT)
            self.image = faded

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def _spawn_enemy_attack_hitbox(self, groups, damage, w=None, h=None, state=None):
        """Spawn an enemy melee attack hitbox, reading size from metadata when possible."""
        sn = state or getattr(self.animator, 'state', None)
        entry = self.animator.states_config.get(sn, {}) \
            if hasattr(self.animator, 'states_config') else {}
        w = entry.get('hitbox_w', w or 50)
        h = entry.get('hitbox_h', h or 46)
        offset_x = entry.get('hitbox_offset_x', 0)
        offset_y = entry.get('hitbox_offset_y', 0)
        
        pivot_x, pivot_y = self._get_true_pivot()
        
        if self.facing == 1:
            hb_x = pivot_x + offset_x
        else:
            hb_x = pivot_x - offset_x - w
        hb_y = pivot_y - h // 2 + offset_y
        
        hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=damage, duration=100)
        groups['enemy_attacks'].add(hitbox)

    def on_death(self):
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0
        self.combo_step = 0


# ── Phase 1 New Monster: Cyclop ───────────────────────────────────────────────

class Cyclop(pygame.sprite.Sprite, HealthMixin):
    """Heavy melee enemy. attack1 is the normal attack. attack2 is a powerful
    special attack gated behind CYCLOP_SPECIAL_COOLDOWN. Stun-immune during
    attack2 and triggers a camera shake."""

    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=120)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.speed = 0.8
        self.facing = -1
        self.attack_timer = 0
        self.special_attack_timer = 0
        self.vel = pygame.math.Vector2(0, 0)
        self.hurt_timer = 0
        self.ai_state = 'chase'
        self.ai_timer = 0
        self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
        self.has_attacked = False
        self.combo_step = 0
        self.dying = False
        self.death_fade_timer = 0
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=44, default_h=110, default_ox=0)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox
        self.camera_shake_triggered = False

    @property
    def foot_y(self):
        return self.hurtbox.bottom

    def load_assets(self):
        anim_config = load_character_animations('cyclop')
        self.animator = Animator.from_config(anim_config)

    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0:
            return
        self._ensure_health_bar()
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        else:
            if self.animator.state == 'attack2':
                if self.health_bar is not None:
                    self.health_bar.notify_damage(self.hp)
                return
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            knockback_dir = 1 if (source_x is not None and self.rect.centerx > source_x) else -1
            self.vel.x = knockback_dir * 1.0
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration
            self.combo_step = 0
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        if self.hp <= 0 or self.animator.state == 'death':
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)
            if not self.dying:
                self.update_animation(dt)
                if self.animator.is_finished():
                    self.dying = True
                    self.death_fade_timer = 0
            else:
                self.death_fade_timer += dt
                if self.death_fade_timer > self.death_fade_delay:
                    fade_progress = (self.death_fade_timer - self.death_fade_delay) / self.death_fade_duration
                    self.alpha = max(0, int(255 * (1.0 - fade_progress)))
                    self._apply_alpha()
                    if self.alpha <= 0:
                        self.kill()
            return

        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.85
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
            if self.hurt_timer <= 0:
                self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        current_attack = self.animator.state
        if current_attack in ('attack1', 'attack2'):
            if self.animator.is_at_hit_frame() and not self.has_attacked:
                if current_attack == 'attack2':
                    damage = 25
                    self.camera_shake_triggered = True
                else:
                    damage = 15
                    self.camera_shake_triggered = False
                self._spawn_enemy_attack_hitbox(groups, damage)
                self.has_attacked = True
            else:
                self.camera_shake_triggered = False
            self.update_animation(dt)
            if self.animator.is_finished():
                self.combo_step = 0
                self.camera_shake_triggered = False
                self.animator.set_state('idle', reset=False)
                self.ai_state = 'wait'
                self.ai_timer = random.randint(800, 1500)
            return

        self.camera_shake_triggered = False
        self.ai_timer -= dt

        if self.ai_state == 'wait':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
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

        moving = False
        self.vel.x = 0
        self.vel.y = 0
        if player is not None and player.hp > 0:
            target_x = player.rect.centerx + self.target_offset.x
            target_y = player.rect.bottom + self.target_offset.y
            dist_x = target_x - self.rect.centerx
            dist_y = target_y - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)
            real_dist_x = player.rect.centerx - self.rect.centerx
            real_dist_y = player.rect.bottom - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)

            if abs(real_dist_x) > CYCLOP_ATTACK_RANGE_X or abs(real_dist_y) > CYCLOP_ATTACK_RANGE_Y:
                if abs(dist_x) > 5:
                    if dist_x < 0:
                        self.rect.x -= self.speed
                        self.facing = -1
                    else:
                        self.rect.x += self.speed
                        self.facing = 1
                    moving = True
                if abs(dist_y) > 5:
                    self.rect.y += self.speed if dist_y > 0 else -self.speed
                    moving = True
                if random.random() < 0.005:
                    self.ai_state = 'idle'
                    self.ai_timer = random.randint(1000, 2000)
            else:
                now = pygame.time.get_ticks()
                if now - self.attack_timer > 2000:
                    special_ready = (now - self.special_attack_timer) > CYCLOP_SPECIAL_COOLDOWN
                    use_special = special_ready and random.random() < 0.35
                    if use_special:
                        self.animator.set_state('attack2', reset=True)
                        self.special_attack_timer = now
                    else:
                        self.animator.set_state('attack1', reset=True)
                    self.has_attacked = False
                    self.attack_timer = now

        if moving:
            self.animator.set_state('run', reset=False)
        else:
            if self.animator.state not in ('attack1', 'attack2', 'hit', 'death'):
                self.animator.set_state('idle', reset=False)

        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
        self.update_animation(dt)

    def update_animation(self, dt):
        if getattr(self, 'animator', None) is not None:
            self.animator.update(dt)
            pdx_old = getattr(self, 'current_pdx', 0)
            pdy_old = getattr(self, 'current_pdy', 0)
            self.rect.x -= pdx_old
            self.rect.y -= pdy_old
            mid = self.rect.midbottom
            frame = self.animator.get_frame()
            pdx, pdy = self.animator.get_pivot_delta()
            if self.facing == -1:
                frame = pygame.transform.flip(frame, True, False)
                pdx = -pdx
            self.image = frame
            self.rect = self.image.get_rect(midbottom=mid)
            self.rect.x += pdx
            self.rect.y += pdy
            self.current_pdx = pdx
            self.current_pdy = pdy
            self._update_hurtbox()

    def _apply_alpha(self):
        if self.image is not None:
            faded = self.image.copy()
            faded.fill((255, 255, 255, self.alpha), special_flags=pygame.BLEND_RGBA_MULT)
            self.image = faded

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def _spawn_enemy_attack_hitbox(self, groups, damage, w=None, h=None, state=None):
        """Spawn an enemy melee attack hitbox, reading size from metadata when possible."""
        sn = state or getattr(self.animator, 'state', None)
        entry = self.animator.states_config.get(sn, {}) \
            if hasattr(self.animator, 'states_config') else {}
        w = entry.get('hitbox_w', w or 60)
        h = entry.get('hitbox_h', h or 55)
        offset_x = entry.get('hitbox_offset_x', 0)
        offset_y = entry.get('hitbox_offset_y', 0)
        
        pivot_x, pivot_y = self._get_true_pivot()
        
        if self.facing == 1:
            hb_x = pivot_x + offset_x
        else:
            hb_x = pivot_x - offset_x - w
        hb_y = pivot_y - h // 2 + offset_y
        
        hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=damage, duration=100)
        groups['enemy_attacks'].add(hitbox)

    def on_death(self):
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0
        self.combo_step = 0


# ── Phase 1 New Monster: Kobold (Assassin) ────────────────────────────────────

class Kobold(pygame.sprite.Sprite, HealthMixin):
    """Assassin enemy with a cooldown-gated dash special attack.
    AI states:
      'chase'         -- walk toward player
      'dash_special'  -- lunge animation + hitbox, moves toward player during frames
      'jump_escape'   -- jump animation, moves away to reset distance
      'attack'        -- 3-hit normal melee combo (attack1 -> attack2 -> attack3)
      'wait'/'idle'   -- brief pause after attacks
    """

    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=35)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.speed = 2.0
        self.facing = -1
        self.attack_timer = 0
        self.dash_timer = 0
        self.vel = pygame.math.Vector2(0, 0)
        self.hurt_timer = 0
        self.ai_state = 'chase'
        self.ai_timer = 0
        self.target_offset = pygame.math.Vector2(random.randint(-20, 20), random.randint(-10, 10))
        self.has_attacked = False
        self.combo_step = 0
        self.dash_exact_x = 0.0
        self.dash_exact_y = 0.0
        self.dash_dx = 0.0
        self.dash_dy = 0.0
        self.dying = False
        self.death_fade_timer = 0
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=26, default_h=72, default_ox=0)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox

    @property
    def foot_y(self):
        return self.hurtbox.bottom

    def load_assets(self):
        anim_config = load_character_animations('kobold')
        self.animator = Animator.from_config(anim_config)

    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0:
            return
        self._ensure_health_bar()
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        else:
            if self.animator.state in ('dash', 'dash_special', 'jump'):
                self.ai_state = 'chase'
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            knockback_dir = 1 if (source_x is not None and self.rect.centerx > source_x) else -1
            self.vel.x = knockback_dir * 2.5
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration
            self.combo_step = 0
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        if self.hp <= 0 or self.animator.state == 'death':
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)
            if not self.dying:
                self.update_animation(dt)
                if self.animator.is_finished():
                    self.dying = True
                    self.death_fade_timer = 0
            else:
                self.death_fade_timer += dt
                if self.death_fade_timer > self.death_fade_delay:
                    fade_progress = (self.death_fade_timer - self.death_fade_delay) / self.death_fade_duration
                    self.alpha = max(0, int(255 * (1.0 - fade_progress)))
                    self._apply_alpha()
                    if self.alpha <= 0:
                        self.kill()
            return

        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.8
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
            if self.hurt_timer <= 0:
                self.animator.set_state('idle', reset=False)
                self.ai_state = 'chase'
            self.update_animation(dt)
            return

        current_state = self.animator.state

        # Dash movement
        if current_state == 'dash':
            # move towards player during dash animation
            self.dash_exact_x += self.dash_dx * (dt / 16.666)
            self.dash_exact_y += self.dash_dy * (dt / 16.666)
            int_x = int(self.dash_exact_x)
            int_y = int(self.dash_exact_y)
            self.rect.x += int_x
            self.rect.y += int_y
            self.dash_exact_x -= int_x
            self.dash_exact_y -= int_y

            self.update_animation(dt)
            if self.animator.is_finished():
                self.animator.set_state('dash_special', reset=True)
                self.has_attacked = False
                self.dash_exact_x = 0.0
                self.dash_exact_y = 0.0
                # turn around to attack the player
                if player is not None:
                    dist_to_player = player.rect.centerx - self.rect.centerx
                    self.facing = 1 if dist_to_player > 0 else -1
                else:
                    self.facing = -self.facing
            return

        # Dash special attack (no movement, just the strike)
        if current_state == 'dash_special':
            if self.animator.is_at_hit_frame() and not self.has_attacked:
                self._spawn_enemy_attack_hitbox(groups, 18)
                self.has_attacked = True

            self.update_animation(dt)
            if self.animator.is_finished():
                self.ai_state = 'jump_escape'
                self.animator.set_state('jump', reset=True)
                self.dash_exact_x = 0.0
                self.dash_exact_y = 0.0
                self.dash_dx = -self.facing * 3.5
                self.dash_dy = 0.0
            return

        # Jump escape
        if current_state == 'jump' and self.ai_state == 'jump_escape':
            self.dash_exact_x += self.dash_dx * (dt / 16.666)
            int_x = int(self.dash_exact_x)
            self.rect.x += int_x
            self.dash_exact_x -= int_x
            self.update_animation(dt)
            if self.animator.is_finished():
                self.ai_state = 'wait'
                self.ai_timer = random.randint(400, 800)
                self.animator.set_state('idle', reset=False)
            return

        # Normal melee combo
        if current_state in ('attack1', 'attack2', 'attack3'):
            if self.animator.is_at_hit_frame() and not self.has_attacked:
                damage = {1: 8, 2: 10, 3: 12}.get(self.combo_step, 8)
                self._spawn_enemy_attack_hitbox(groups, damage)
                self.has_attacked = True
            self.update_animation(dt)
            if self.animator.is_finished():
                dist_x = player.hurtbox.centerx - self.hurtbox.centerx
                dist_y = player.hurtbox.bottom - self.hurtbox.bottom
                in_range = abs(dist_x) <= KOBOLD_ATTACK_RANGE_X and abs(dist_y) <= KOBOLD_ATTACK_RANGE_Y
                if in_range and self.combo_step < 3:
                    self.combo_step += 1
                    self.animator.set_state(f'attack{self.combo_step}', reset=True)
                    self.has_attacked = False
                else:
                    self.combo_step = 0
                    self.animator.set_state('idle', reset=False)
                    self.ai_state = 'wait'
                    self.ai_timer = random.randint(400, 800)
            return

        self.ai_timer -= dt

        if self.ai_state == 'wait':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
                self.target_offset = pygame.math.Vector2(random.randint(-20, 20), random.randint(-10, 10))
            self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        if self.ai_state == 'idle':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
            self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        moving = False
        self.vel.x = 0
        self.vel.y = 0
        if player is not None and player.hp > 0:
            real_dist_x = player.rect.centerx - self.rect.centerx
            real_dist_y = player.rect.bottom - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)
            target_x = player.rect.centerx + self.target_offset.x
            target_y = player.rect.bottom + self.target_offset.y
            dist_x = target_x - self.rect.centerx
            dist_y = target_y - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)
            now = pygame.time.get_ticks()

            # Melee range - normal combo
            if abs(real_dist_x) <= KOBOLD_ATTACK_RANGE_X and abs(real_dist_y) <= KOBOLD_ATTACK_RANGE_Y:
                if now - self.attack_timer > 1200:
                    self.combo_step = 1
                    self.animator.set_state('attack1', reset=True)
                    self.has_attacked = False
                    self.attack_timer = now

            # Dash range - dash special if cooldown ready
            elif abs(real_dist_x) <= KOBOLD_DASH_RANGE_X and abs(real_dist_y) <= KOBOLD_DASH_RANGE_Y:
                if (now - self.dash_timer) > KOBOLD_DASH_COOLDOWN:
                    # Dash EXACTLY behind the player based on PLAYER's facing
                    player_facing = getattr(player, 'facing', 1)
                    overshoot = 100
                    target_x = player.rect.centerx - (player_facing * overshoot)
                    target_dist_x = target_x - self.rect.centerx
                    
                    self.facing = 1 if target_dist_x > 0 else -1
                    self.dash_exact_x = 0.0
                    self.dash_exact_y = 0.0
                    
                    total_frames_approx = len(self.animator.states.get('dash', [1]))
                    duration_ms = self.animator.durations.get('dash', 100)
                    total_time_ms = max(total_frames_approx * duration_ms, 1)
                    total_ticks = total_time_ms / 16.666
                    
                    self.dash_dx = target_dist_x / total_ticks
                    self.dash_dy = real_dist_y / total_ticks
                    self.animator.set_state('dash', reset=True)
                    self.has_attacked = False
                    self.dash_timer = now
                    self.ai_timer = 0
                else:
                    # Dash on cooldown - walk toward player
                    if abs(dist_x) > 5:
                        if dist_x < 0:
                            self.rect.x -= self.speed
                            self.facing = -1
                        else:
                            self.rect.x += self.speed
                            self.facing = 1
                        moving = True
                    if abs(dist_y) > 5:
                        self.rect.y += self.speed if dist_y > 0 else -self.speed
                        moving = True
            else:
                # Out of dash range - just chase
                if abs(dist_x) > 5:
                    if dist_x < 0:
                        self.rect.x -= self.speed
                        self.facing = -1
                    else:
                        self.rect.x += self.speed
                        self.facing = 1
                    moving = True
                if abs(dist_y) > 5:
                    self.rect.y += self.speed if dist_y > 0 else -self.speed
                    moving = True
                if random.random() < 0.005:
                    self.ai_state = 'idle'
                    self.ai_timer = random.randint(800, 1500)

        if moving:
            self.animator.set_state('run', reset=False)
        else:
            if self.animator.state not in ('attack1', 'attack2', 'attack3',
                                            'dash', 'dash_special', 'jump', 'hit', 'death'):
                self.animator.set_state('idle', reset=False)

        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
        self.update_animation(dt)

    def update_animation(self, dt):
        if getattr(self, 'animator', None) is not None:
            self.animator.update(dt)
            pdx_old = getattr(self, 'current_pdx', 0)
            pdy_old = getattr(self, 'current_pdy', 0)
            self.rect.x -= pdx_old
            self.rect.y -= pdy_old
            mid = self.rect.midbottom
            frame = self.animator.get_frame()
            pdx, pdy = self.animator.get_pivot_delta()
            if self.facing == -1:
                frame = pygame.transform.flip(frame, True, False)
                pdx = -pdx
            self.image = frame
            self.rect = self.image.get_rect(midbottom=mid)
            self.rect.x += pdx
            self.rect.y += pdy
            self.current_pdx = pdx
            self.current_pdy = pdy
            self._update_hurtbox()

    def _apply_alpha(self):
        if self.image is not None:
            faded = self.image.copy()
            faded.fill((255, 255, 255, self.alpha), special_flags=pygame.BLEND_RGBA_MULT)
            self.image = faded

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def _spawn_enemy_attack_hitbox(self, groups, damage, w=None, h=None, state=None):
        """Spawn an enemy melee attack hitbox, reading size from metadata when possible."""
        sn = state or getattr(self.animator, 'state', None)
        entry = self.animator.states_config.get(sn, {}) \
            if hasattr(self.animator, 'states_config') else {}
        w = entry.get('hitbox_w', w or 45)
        h = entry.get('hitbox_h', h or 42)
        offset_x = entry.get('hitbox_offset_x', 0)
        offset_y = entry.get('hitbox_offset_y', 0)
        
        pivot_x, pivot_y = self._get_true_pivot()
        
        if self.facing == 1:
            hb_x = pivot_x + offset_x
        else:
            hb_x = pivot_x - offset_x - w
        hb_y = pivot_y - h // 2 + offset_y
        
        hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=damage, duration=100)
        groups['enemy_attacks'].add(hitbox)

    def on_death(self):
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0
        self.combo_step = 0


# ── Phase 1 New Monster: Fireworm (Ranged) ────────────────────────────────────

class Fireworm(pygame.sprite.Sprite, HealthMixin):
    """Ranged enemy that throws fireballs. Same logic as GoblinSpearman but
    uses FIREWORM_ATTACK_RANGE (shorter) and spawns animated Fireball."""

    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=30)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.speed = 1.0
        self.facing = -1
        self.attack_timer = 0
        self.vel = pygame.math.Vector2(0, 0)
        self.hurt_timer = 0
        self.ai_state = 'chase'
        self.ai_timer = 0
        self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
        self.has_attacked = False
        self.dying = False
        self.death_fade_timer = 0
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=30, default_h=70, default_ox=0)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox
        self._fireball_frame = 12

    @property
    def foot_y(self):
        return self.hurtbox.bottom

    def load_assets(self):
        anim_config = load_character_animations('fireworm')
        self.animator = Animator.from_config(anim_config)

    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0:
            return
        self._ensure_health_bar()
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        else:
            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            knockback_dir = 1 if (source_x is not None and self.rect.centerx > source_x) else -1
            self.vel.x = knockback_dir * 2.0
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        if self.hp <= 0 or self.animator.state == 'death':
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)
            if not self.dying:
                self.update_animation(dt)
                if self.animator.is_finished():
                    self.dying = True
                    self.death_fade_timer = 0
            else:
                self.death_fade_timer += dt
                if self.death_fade_timer > self.death_fade_delay:
                    fade_progress = (self.death_fade_timer - self.death_fade_delay) / self.death_fade_duration
                    self.alpha = max(0, int(255 * (1.0 - fade_progress)))
                    self._apply_alpha()
                    if self.alpha <= 0:
                        self.kill()
            return

        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.8
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
            if self.hurt_timer <= 0:
                self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        if self.animator.state == 'attack':
            if self.animator.frame_index == self._fireball_frame and not self.has_attacked:
                fb = Fireball(self.rect.centerx, self.rect.centery,
                              player.rect.centerx, player.rect.centery)
                fb.owner = self
                if 'enemy_projectiles' in groups:
                    groups['enemy_projectiles'].add(fb)
                self.has_attacked = True
            self.update_animation(dt)
            if self.animator.is_finished():
                self.animator.set_state('idle', reset=False)
                self.ai_state = 'wait'
                self.ai_timer = random.randint(1000, 2000)
            return

        self.ai_timer -= dt

        if self.ai_state == 'wait':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
                self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
            self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        if self.ai_state == 'idle':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
            self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        moving = False
        self.vel.x = 0
        self.vel.y = 0
        if player is not None and player.hp > 0:
            dx = player.rect.centerx - self.rect.centerx
            dy = player.rect.centery - self.rect.centery
            dist = math.hypot(dx, dy)

            if dist > FIREWORM_ATTACK_RANGE:
                target_x = player.rect.centerx + self.target_offset.x
                target_y = player.rect.bottom + self.target_offset.y
                dist_x = target_x - self.rect.centerx
                dist_y = target_y - self.rect.bottom
                if abs(dist_x) > 5:
                    if dist_x < 0:
                        self.rect.x -= self.speed
                        self.facing = -1
                    else:
                        self.rect.x += self.speed
                        self.facing = 1
                    moving = True
                if abs(dist_y) > 5:
                    self.rect.y += self.speed if dist_y > 0 else -self.speed
                    moving = True
                if random.random() < 0.005:
                    self.ai_state = 'idle'
                    self.ai_timer = random.randint(1000, 2000)
            else:
                if pygame.time.get_ticks() - self.attack_timer > 2500:
                    self.animator.set_state('attack', reset=True)
                    self.has_attacked = False
                    self.attack_timer = pygame.time.get_ticks()

        if moving:
            self.animator.set_state('run', reset=False)
        else:
            if self.animator.state not in ('attack', 'hit', 'death'):
                self.animator.set_state('idle', reset=False)

        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))
        self.update_animation(dt)

    def update_animation(self, dt):
        if getattr(self, 'animator', None) is not None:
            self.animator.update(dt)
            pdx_old = getattr(self, 'current_pdx', 0)
            pdy_old = getattr(self, 'current_pdy', 0)
            self.rect.x -= pdx_old
            self.rect.y -= pdy_old
            mid = self.rect.midbottom
            frame = self.animator.get_frame()
            pdx, pdy = self.animator.get_pivot_delta()
            if self.facing == -1:
                frame = pygame.transform.flip(frame, True, False)
                pdx = -pdx
            self.image = frame
            self.rect = self.image.get_rect(midbottom=mid)
            self.rect.x += pdx
            self.rect.y += pdy
            self.current_pdx = pdx
            self.current_pdy = pdy
            self._update_hurtbox()

    def _apply_alpha(self):
        if self.image is not None:
            faded = self.image.copy()
            faded.fill((255, 255, 255, self.alpha), special_flags=pygame.BLEND_RGBA_MULT)
            self.image = faded

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def on_death(self):
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0


# ── Fireball animated projectile ─────────────────────────────────────────────

class Fireball(pygame.sprite.Sprite):
    """Animated fireball projectile spawned by Fireworm.
    Plays the 'move' animation loop while travelling, and 'explosion'
    on impact (handled externally; this sprite self-kills off-screen)."""

    def __init__(self, x, y, target_x, target_y, damage=12):
        super().__init__()
        anim_config = load_character_animations('fireball')
        self.animator = Animator.from_config(anim_config)
        self.animator.set_state('move', reset=True)
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(center=(x, y))
        self.damage = damage

        direction = pygame.math.Vector2(target_x - x, target_y - y)
        if direction.length() > 0:
            direction = direction.normalize()
        else:
            direction = pygame.math.Vector2(1, 0)
        self.vel = direction * FIREBALL_SPEED
        self.facing = 1 if direction.x >= 0 else -1

    @property
    def y(self):
        return self.rect.centery

    @property
    def floor_y(self):
        return self.rect.centery + 20

    def update(self, dt):
        self.rect.x += int(self.vel.x)
        self.rect.y += int(self.vel.y)
        self.animator.update(dt)
        frame = self.animator.get_frame()
        if self.facing == -1:
            frame = pygame.transform.flip(frame, True, False)
        center = self.rect.center
        self.image = frame
        self.rect = self.image.get_rect(center=center)
        from config import WIDTH, HEIGHT
        if self.rect.right < 0 or self.rect.left > WIDTH or self.rect.bottom < 0 or self.rect.top > HEIGHT:
            self.kill()


class Arrow(pygame.sprite.Sprite):
    ARROW_SCALE = 2.5  # match the archer's sprite scale

    def __init__(self, x, y, facing, damage=15, owner=None, arrow_type='normal'):
        super().__init__()
        self.arrow_type = arrow_type if arrow_type in ARCHER_ARROW_CONFIG else 'normal'
        arrow_cfg = ARCHER_ARROW_CONFIG[self.arrow_type]
        try:
            raw = pygame.image.load(arrow_cfg['path']).convert_alpha()
            # Magic Arrow artwork has a larger canvas than the standard arrow.
            # Keep every arrow within the same readable projectile footprint.
            scale = self.ARROW_SCALE if self.arrow_type == 'normal' else min(1.0, 56 / max(raw.get_width(), raw.get_height()))
            aw = max(1, int(raw.get_width() * scale))
            ah = max(1, int(raw.get_height() * scale))
            self.image = pygame.transform.scale(raw, (aw, ah))
        except Exception:
            self.image = pygame.Surface((65, 8))
            self.image.fill(arrow_cfg.get('hud_color', (200, 200, 200)))

        if facing == -1:
            self.image = pygame.transform.flip(self.image, True, False)

        self.rect = self.image.get_rect(center=(x, y))
        self.facing = facing
        self.speed = 20
        self.damage = damage
        self.owner = owner

    @property
    def y(self):
        """Vertical screen position of the projectile centre."""
        return self.rect.centery

    @property
    def floor_y(self):
        """Ground-plane projection: the Y row this arrow travels on."""
        return self.rect.centery + 25

    def update(self, dt):
        self.rect.x += self.speed * self.facing
        if self.rect.right < 0 or self.rect.left > MAX_X:
            self.kill()


class Spear(pygame.sprite.Sprite):
    SPEAR_SCALE = 2.0

    def __init__(self, x, y, target_x, target_y, damage=10):
        super().__init__()
        try:
            raw = pygame.image.load(SPEAR_IMAGE).convert_alpha()
            sw = int(raw.get_width() * self.SPEAR_SCALE)
            sh = int(raw.get_height() * self.SPEAR_SCALE)
            self.image = pygame.transform.scale(raw, (sw, sh))
        except Exception:
            self.image = pygame.Surface((40, 6))
            self.image.fill((150, 150, 150))

        direction = pygame.math.Vector2(target_x - x, target_y - y)
        if direction.length() > 0:
            direction = direction.normalize()
        else:
            direction = pygame.math.Vector2(1, 0)
        self.vel = direction * 10
        
        angle = math.degrees(math.atan2(-direction.y, direction.x))
        self.image = pygame.transform.rotate(self.image, angle)
        self.rect = self.image.get_rect(center=(x, y))
        self.damage = damage

    @property
    def y(self):
        """Vertical screen position of the projectile centre."""
        return self.rect.centery

    @property
    def floor_y(self):
        """Ground-plane projection: the Y row this spear travels on."""
        return self.rect.centery + 25

    def update(self, dt):
        self.rect.x += int(self.vel.x)
        self.rect.y += int(self.vel.y)
        from config import WIDTH, HEIGHT
        if self.rect.right < 0 or self.rect.left > WIDTH or self.rect.bottom < 0 or self.rect.top > HEIGHT:
            self.kill()


class DashSmoke(pygame.sprite.Sprite):
    """One-shot dash smoke puff left behind the archer when she dashes.

    Loaded dynamically from animation_metadata.json (dash_smoke).
    Renders in Y-sorted order via *floor_y* but has no hurtbox, so no shadow
    is drawn beneath it.
    """
    _frames_cache = None  # class-level cache so the strip is sliced only once

    @classmethod
    def _get_meta(cls):
        from sprites import _ANIMATION_METADATA
        return _ANIMATION_METADATA.get('archer', {}).get('animations', {}).get('dash_smoke', {})

    def __init__(self, x, y, facing):
        super().__init__()
        meta = self._get_meta()
        self.frame_duration = meta.get('duration', 55)

        # You can adjust the offset of the smoke in assets/animation_metadata.json 
        # using the "offset_x" and "offset_y" variables under "dash_smoke".
        # positive offset_x moves smoke RIGHT (flips automatically with facing direction)
        # positive offset_y moves smoke DOWN
        self.offset_x = meta.get('offset_x', 0)
        self.offset_y = meta.get('offset_y', 0)

        frames = self._load_frames()
        if not frames:
            # Fallback invisible surface
            self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
            self._frames = []
        else:
            self._frames = frames
            if facing == -1:
                self._frames = [pygame.transform.flip(f, True, False) for f in frames]
            self.image = self._frames[0]

        final_x = x + (self.offset_x * facing)
        final_y = y + self.offset_y
        self.rect = self.image.get_rect(center=(final_x, final_y))
        
        self._frame_index = 0
        self._time = 0
        self._finished = False

    @property
    def floor_y(self):
        """Used by the Y-sort in draw() to place smoke at the right depth."""
        return self.rect.bottom

    @classmethod
    def _load_frames(cls):
        if cls._frames_cache is not None:
            return cls._frames_cache
        meta = cls._get_meta()
        try:
            from sprites import SpriteSheet
            ss = SpriteSheet(DASH_SMOKE_IMAGE)
            frame_count = meta.get('frames', 9)
            scale = meta.get('scale', 1.5)
            cls._frames_cache = ss.load_horizontal_strip(frame_count, scale=scale)
        except Exception as e:
            print(f"[WARNING] DashSmoke: failed to load {DASH_SMOKE_IMAGE}: {e}")
            cls._frames_cache = []
        return cls._frames_cache

    def update(self, dt):
        if self._finished or not self._frames:
            self.kill()
            return
        self._time += dt
        while self._time >= self.frame_duration:
            self._time -= self.frame_duration
            self._frame_index += 1
            if self._frame_index >= len(self._frames):
                self._finished = True
                self.kill()
                return
        self.image = self._frames[self._frame_index]
        self.rect = self.image.get_rect(center=self.rect.center)


class BloodVFX(pygame.sprite.Sprite):
    """Spawns blood effects when an enemy is hit or dies."""
    
    _hit_cache = None
    _death_cache = None
    
    def __init__(self, x, y, facing, foot_y, vfx_type="hit"):
        super().__init__()
        self.frame_duration = 50
        self.timer = 0
        self.frame_index = 0
        self._custom_floor_y = foot_y + 10  # Force it to draw in front of the entity
        
        if vfx_type == "death":
            frames = self._get_death_frames()
        else:
            frames = self._get_hit_frames()
            
        if not frames:
            self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
            self._frames = []
        else:
            self._frames = frames
            # Reverse if facing == 1 per user request
            if facing == 1:
                self._frames = [pygame.transform.flip(f, True, False) for f in frames]
                
            self.image = self._frames[0]
            
        # Move the blood effect slightly to the back of the entity
        x_offset = -facing * 40
        self.rect = self.image.get_rect(center=(x + x_offset, y))

    @property
    def floor_y(self):
        return self._custom_floor_y

    @classmethod
    def _get_hit_frames(cls):
        if cls._hit_cache is not None:
            return cls._hit_cache
        try:
            sheet = pygame.image.load("assets/vfx/hit_blood_vfx.png").convert_alpha()
            frames = [sheet.subsurface((i * 110, 0, 110, 93)) for i in range(5)]
            # Scale up the blood
            cls._hit_cache = [pygame.transform.scale(f, (int(f.get_width() * 1.5), int(f.get_height() * 1.5))) for f in frames]
        except Exception:
            cls._hit_cache = []
        return cls._hit_cache

    @classmethod
    def _get_death_frames(cls):
        if cls._death_cache is not None:
            return cls._death_cache
        try:
            sheet = pygame.image.load("assets/vfx/death_blood_vfx.png").convert_alpha()
            frames = [sheet.subsurface((i * 110, 0, 110, 93)) for i in range(9)]
            # Scale up the blood
            cls._death_cache = [pygame.transform.scale(f, (int(f.get_width() * 1.5), int(f.get_height() * 1.5))) for f in frames]
        except Exception:
            cls._death_cache = []
        return cls._death_cache
        
    def update(self, dt):
        if not self._frames:
            self.kill()
            return
            
        self.timer += dt
        if self.timer >= self.frame_duration:
            self.timer -= self.frame_duration
            self.frame_index += 1
            if self.frame_index >= len(self._frames):
                self.kill()
            else:
                self.image = self._frames[self.frame_index]

class HitVFX(pygame.sprite.Sprite):
    """Spawns generic hit flash effects when an entity is struck."""
    
    _frames_cache = None
    
    def __init__(self, x, y, facing, foot_y):
        super().__init__()
        self.frame_duration = 40
        self.timer = 0
        self.frame_index = 0
        self._custom_floor_y = foot_y + 12  # Force it to draw in front
        
        frames = self._get_frames()
        if not frames:
            self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
            self._frames = []
        else:
            self._frames = frames
            # Reverse if facing == 1 per user request
            if facing == 1:
                self._frames = [pygame.transform.flip(f, True, False) for f in frames]
            self.image = self._frames[0]
            
        self.rect = self.image.get_rect(center=(x, y))

    @property
    def floor_y(self):
        return self._custom_floor_y

    @classmethod
    def _get_frames(cls):
        if cls._frames_cache is not None:
            return cls._frames_cache
        try:
            sheet = pygame.image.load("assets/vfx/hit_vfx.png").convert_alpha()
            # 336x48 -> 7 frames of 48x48
            frames = [sheet.subsurface((i * 48, 0, 48, 48)) for i in range(7)]
            # Scale it up
            cls._frames_cache = [pygame.transform.scale(f, (int(f.get_width() * 1.5), int(f.get_height() * 1.5))) for f in frames]
        except Exception:
            cls._frames_cache = []
        return cls._frames_cache
        
    def update(self, dt):
        if not self._frames:
            self.kill()
            return
            
        self.timer += dt
        if self.timer >= self.frame_duration:
            self.timer -= self.frame_duration
            self.frame_index += 1
            if self.frame_index >= len(self._frames):
                self.kill()
            else:
                self.image = self._frames[self.frame_index]

class UltimateEffect(pygame.sprite.Sprite):
    """Animated stretching beam fired during the archer's ultimate.

    Loaded dynamically from animation_metadata.json (ultimate_effect).
    Stays fixed at the spawn position — the animation itself stretches
    outward as a beam.  Damages every enemy whose hurtbox overlaps the
    beam rect, hitting each enemy only ONCE for the duration of the cast.
    Removes itself when the animation finishes.
    """
    _frames_cache_right = None
    _frames_cache_left  = None

    @classmethod
    def _get_meta(cls):
        from sprites import _ANIMATION_METADATA
        return _ANIMATION_METADATA.get('archer', {}).get('animations', {}).get('ultimate_effect', {})

    def __init__(self, x, y, facing):
        super().__init__()
        meta = self._get_meta()
        self.frame_duration = meta.get('duration', 80)
        self.facing = facing
        self.damage = ARCHER_ULTIMATE_DAMAGE
        # Each enemy may be hit only once per beam cast
        self.already_hit_targets: set = set()
        
        self.offset_x = meta.get('offset_x', 0)
        self.offset_y = meta.get('offset_y', 0)

        frames = self._load_frames(facing)
        if not frames:
            self.image = pygame.Surface((80, 16), pygame.SRCALPHA)
            self._frames = []
        else:
            self._frames = frames
            self.image = self._frames[0]

        # Anchor beam to the side of the archer's hurtbox, then apply offset
        final_x = x + (self.offset_x * facing)
        final_y = y + self.offset_y
        if facing == 1:
            self.rect = self.image.get_rect(midleft=(final_x, final_y))
        else:
            self.rect = self.image.get_rect(midright=(final_x, final_y))
        self._frame_index = 0
        self._time = 0

    @property
    def floor_y(self):
        return self.rect.centery + 20

    @classmethod
    def _load_frames(cls, facing):
        if facing == 1:
            if cls._frames_cache_right is not None:
                return cls._frames_cache_right
        else:
            if cls._frames_cache_left is not None:
                return cls._frames_cache_left

        meta = cls._get_meta()
        try:
            from sprites import SpriteSheet
            ss = SpriteSheet(ULTIMATE_EFFECT_IMAGE)
            frame_count = meta.get('frames', 7)
            scale = meta.get('scale', 2.5)
            base = ss.load_horizontal_strip(frame_count, scale=scale)
        except Exception as e:
            print(f"[WARNING] UltimateEffect: failed to load {ULTIMATE_EFFECT_IMAGE}: {e}")
            base = []

        cls._frames_cache_right = base
        cls._frames_cache_left  = [pygame.transform.flip(f, True, False) for f in base] if base else []
        return cls._frames_cache_right if facing == 1 else cls._frames_cache_left

    def update(self, dt):
        # Advance animation (non-looping — kill when finished)
        if self._frames:
            self._time += dt
            while self._time >= self.frame_duration:
                self._time -= self.frame_duration
                self._frame_index += 1
                if self._frame_index >= len(self._frames):
                    self.kill()
                    return
            self.image = self._frames[self._frame_index]
        else:
            self.kill()

    def can_hit(self, enemy):
        """Returns True if this enemy has not yet been hit by this beam."""
        return id(enemy) not in self.already_hit_targets

    def register_hit(self, enemy):
        """Mark this enemy as hit — prevents hitting them again this cast."""
        self.already_hit_targets.add(id(enemy))


class Archer(pygame.sprite.Sprite, HealthMixin):

    def __init__(self, pos=(200, 300)):
        pygame.sprite.Sprite.__init__(self)
        _preset = PLAYER_RESOURCE_PRESETS.get('archer', {})
        HealthMixin.__init__(
            self,
            max_hp=80,
            max_armor=_preset.get('max_armor', 45),
            max_mana=_preset.get('max_mana', 120),
            armor_reduction_pct=_preset.get('armor_reduction_pct', 0.30),
        )
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.vel = pygame.math.Vector2(0, 0)
        self.speed = 5
        self.facing = 1
        self.on_ground = True
        self.controls = {
            'left': [pygame.K_LEFT],
            'right': [pygame.K_RIGHT],
            'up': [pygame.K_UP],
            'down': [pygame.K_DOWN],
            'attack': [pygame.K_KP1, pygame.K_KP4],
            'dash': [pygame.K_KP2, pygame.K_KP5],
            'ultimate': [pygame.K_KP3, pygame.K_KP6],
        }

        self.hurt_timer = 0

        # -- Attack / Combo --
        # combo_step: 0 = none, 1 = 'attack', 2 = 'attack_combo'
        self.combo_step = 0
        self.combo_buffered = False
        self.attack_pressed_last = False
        # Per-frame arrow spawn guards
        self._arrow_shot_f5  = False   # 'attack'       frame 5
        self._arrow_shot_f11 = False   # 'attack_combo' frame 11
        self._arrow_shot_f14 = False   # 'attack_combo' frame 14

        # -- Dash --
        self.dash_cooldown = 0
        self.dash_dx = 0
        self.dash_dy = 0
        self.dashing = False

        # -- Ultimate --
        self.ultimate_cooldown = 0
        self.ultimate_pressed_last = False
        self._ultimate_beam_spawned = False
        
        # -- Skills Inventory --
        self.skills = []  # List of skill types that have been picked up
        self.active_skill = None  # Currently selected skill (if any)
        self.target_skill_idx = 0  # Selected skill slot index (0..2)

        # Magic Arrow selection. Numpad 0 cycles this list during gameplay.
        self.arrow_types = list(ARCHER_ARROW_CONFIG.keys())
        self.arrow_type_index = 0
        self.arrow_type = self.arrow_types[self.arrow_type_index]

        # -- Hurtbox --
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=40, default_h=80, default_ox=-5)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox

    @property
    def foot_y(self):
        """Ground-plane Y position of this character (pivot-corrected foot)."""
        return self.hurtbox.bottom

    def _is_control_pressed(self, control_name, keys):
        for key in self.controls.get(control_name, []):
            if keys[key]:
                return True
        return False

    def load_assets(self):
        anim_config = load_character_animations('archer')
        self.animator = Animator.from_config(anim_config)

    def _apply_frame(self):
        """Apply current animation frame with pivot alignment correction."""
        pdx_old = getattr(self, 'current_pdx', 0)
        pdy_old = getattr(self, 'current_pdy', 0)
        self.rect.x -= pdx_old
        self.rect.y -= pdy_old

        mid = self.rect.midbottom
        frame = self.animator.get_frame()
        pdx, pdy = self.animator.get_pivot_delta()
        if self.facing == -1:
            frame = pygame.transform.flip(frame, True, False)
            pdx = -pdx
        self.image = frame
        self.rect = self.image.get_rect(midbottom=mid)
        self.rect.x += pdx
        self.rect.y += pdy
        self.current_pdx = pdx
        self.current_pdy = pdy
        self._update_hurtbox()

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def _clamp_position(self):
        self.rect.left   = max(MIN_X, self.rect.left)
        self.rect.right  = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))

    def take_damage(self, amount, source_x=None, is_crit=False):
        # Invincibility during dash and ultimate
        if self.hp <= 0 or self.dashing or self.animator.state == 'ultimate':
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

    def update(self, dt, keys=None, groups=None):
        if keys is None or groups is None:
            return

        # Dead: play death animation only
        if self.hp <= 0:
            if getattr(self, 'animator', None) is not None:
                self.animator.update(dt)
                self._apply_frame()
            return

        # Cooldown timers
        if self.dash_cooldown > 0:
            self.dash_cooldown -= dt
        if self.ultimate_cooldown > 0:
            self.ultimate_cooldown -= dt

        # DASH block
        if self.dashing:
            self.animator.update(dt)
            dash_speed = 8   # pixels per frame - new 5-frame dash moves every frame
            self.rect.x += int(self.dash_dx * dash_speed)
            self.rect.y += int(self.dash_dy * dash_speed)
            if self.animator.is_finished():
                self.dashing = False
                self.vel.x = 0
                self.vel.y = 0
                self.animator.set_state('idle', reset=False)
            self._apply_frame()
            self._clamp_position()
            return

        # HURT block
        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.8
            if self.hurt_timer <= 0:
                self.animator.set_state('idle', reset=False)
            self.animator.update(dt)
            self._apply_frame()
            self._clamp_position()
            return

        # ULTIMATE block
        if self.animator.state == 'ultimate':
            self.animator.update(dt)
            fi = self.animator.frame_index
            if fi >= ARCHER_ULTIMATE_CAST_FRAME and not self._ultimate_beam_spawned:
                self._spawn_ultimate_beam(groups)
                self._ultimate_beam_spawned = True
            if self.animator.is_finished():
                self.animator.set_state('idle', reset=False)
            self._apply_frame()
            self._clamp_position()
            return

        # Normal input
        self.handle_input(keys, groups)

        # Yield to dash/ultimate if handle_input started them
        if self.dashing or self.animator.state == 'ultimate':
            self.animator.update(dt)
            self._apply_frame()
            self._clamp_position()
            return

        self.rect.x += int(self.vel.x)
        self.rect.y += int(self.vel.y)

        # Attack state machine
        state = self.animator.state

        if state == 'attack':
            fi = self.animator.frame_index
            # Shoot at frame 5
            if fi == 5 and not self._arrow_shot_f5:
                self.spawn_arrow(groups)
                self._arrow_shot_f5 = True
            if fi != 5:
                self._arrow_shot_f5 = False

            if self.animator.is_finished():
                if self.combo_buffered:
                    self.combo_buffered = False
                    self._arrow_shot_f5 = False
                    if self.combo_step < 2:
                        # Play the second basic attack
                        self.combo_step += 1
                        self.animator.set_state('attack', reset=True)
                    else:
                        # Two basic attacks done — fire the combo
                        self.combo_step = 3
                        self.animator.set_state('attack_combo', reset=True)
                        self._arrow_shot_f11 = False
                        self._arrow_shot_f14 = False
                else:
                    self.combo_step = 0
                    self.animator.set_state('idle', reset=False)

        elif state == 'attack_combo':
            fi = self.animator.frame_index
            # First shot at frame 11
            if fi == 11 and not self._arrow_shot_f11:
                self.spawn_arrow(groups)
                self._arrow_shot_f11 = True
            if fi != 11:
                self._arrow_shot_f11 = False
            # Second shot at frame 14
            if fi == 14 and not self._arrow_shot_f14:
                self.spawn_arrow(groups)
                self._arrow_shot_f14 = True
            if fi != 14:
                self._arrow_shot_f14 = False

            if self.animator.is_finished():
                self.combo_step = 0
                self.animator.set_state('idle', reset=False)

        else:
            if abs(self.vel.x) > 0 or abs(self.vel.y) > 0:
                self.animator.set_state('run', reset=False)
            else:
                self.animator.set_state('idle', reset=False)

        self.animator.update(dt)
        self._apply_frame()
        self._clamp_position()

    def handle_input(self, keys, groups):
        self.vel.x = 0
        self.vel.y = 0

        attack_pressed   = self._is_control_pressed('attack', keys)
        ultimate_pressed = self._is_control_pressed('ultimate', keys)
        just_pressed_attack   = attack_pressed   and not self.attack_pressed_last
        just_pressed_ultimate = ultimate_pressed and not self.ultimate_pressed_last
        self.attack_pressed_last   = attack_pressed
        self.ultimate_pressed_last = ultimate_pressed

        state = self.animator.state
        is_attacking = state in ('attack', 'attack_combo', 'ultimate')

        # Dash (K) - highest priority
        if self._is_control_pressed('dash', keys) and self.dash_cooldown <= 0 and not is_attacking:
            self.dash_dx = 0
            self.dash_dy = 0
            if self._is_control_pressed('left', keys):
                self.dash_dx = -1
            if self._is_control_pressed('right', keys):
                self.dash_dx = 1
            if self._is_control_pressed('up', keys):
                self.dash_dy = -1
            if self._is_control_pressed('down', keys):
                self.dash_dy = 1
            if self.dash_dx == 0 and self.dash_dy == 0:
                self.dash_dx = self.facing
            if self.dash_dx != 0:
                self.facing = self.dash_dx

            # Spawn smoke trail behind the archer (facing = dash direction, smoke faces opposite)
            smoke_x = self.hurtbox.centerx - (self.facing * 10)
            smoke_y = self.hurtbox.bottom - 10
            smoke = DashSmoke(smoke_x, smoke_y, self.facing)
            if 'effects' in groups:
                groups['effects'].add(smoke)

            self.animator.set_state('dash', reset=True)
            self.dashing = True
            self.dash_cooldown = 1500
            return

        # Ultimate (L)
        if just_pressed_ultimate and self.ultimate_cooldown <= 0 and not is_attacking:
            self.animator.set_state('ultimate', reset=True)
            self.ultimate_cooldown = ARCHER_ULTIMATE_COOLDOWN
            self._ultimate_beam_spawned = False
            self.vel.x = 0
            self.vel.y = 0
            return

        # Attack (J)
        if just_pressed_attack:
            if state not in ('attack', 'attack_combo', 'ultimate'):
                self.combo_step = 1
                self.animator.set_state('attack', reset=True)
                self._arrow_shot_f5 = False
            elif state == 'attack' and not self.combo_buffered:
                # Buffer the next step (2nd attack, or combo if already on step 2)
                self.combo_buffered = True

        if is_attacking:
            return

        if self._is_control_pressed('left', keys):
            self.vel.x = -self.speed
            self.facing = -1
        if self._is_control_pressed('right', keys):
            self.vel.x = self.speed
            self.facing = 1
        if self._is_control_pressed('up', keys):
            self.vel.y = -self.speed
        if self._is_control_pressed('down', keys):
            self.vel.y = self.speed

    def spawn_arrow(self, groups):
        spawn_y = self.rect.bottom - 6 - self.rect.height // 2
        spawn_x = self.rect.centerx + (20 * self.facing)
        arrow_cfg = ARCHER_ARROW_CONFIG.get(self.arrow_type, ARCHER_ARROW_CONFIG['normal'])
        arrow = Arrow(spawn_x, spawn_y, self.facing, damage=arrow_cfg['damage'], owner=self, arrow_type=self.arrow_type)
        groups['arrows'].add(arrow)

    def cycle_arrow_type(self):
        self.arrow_type_index = (self.arrow_type_index + 1) % len(self.arrow_types)
        self.arrow_type = self.arrow_types[self.arrow_type_index]

    def _spawn_ultimate_beam(self, groups):
        """Spawn the UltimateEffect beam at the archer's chest position."""
        spawn_x = self.hurtbox.right if self.facing == 1 else self.hurtbox.left
        spawn_y = self.hurtbox.centery - 10
        beam = UltimateEffect(spawn_x, spawn_y, self.facing)
        if 'effects' in groups:
            groups['effects'].add(beam)
        if 'ultimate_beams' in groups:
            groups['ultimate_beams'].add(beam)

    def on_death(self):
        print('Archer died')
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0


class GoblinWarrior(pygame.sprite.Sprite, HealthMixin):
    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=50)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.speed = 1.5
        self.facing = -1
        self.attack_timer = 0
        self.vel = pygame.math.Vector2(0, 0)
        self.hurt_timer = 0
        self.ai_state = 'chase'
        self.ai_timer = 0
        self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
        self.has_attacked = False
        self.combo_step = 0
        # Death fade-out state
        self.dying = False
        self.death_fade_timer = 0
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=30, default_h=96, default_ox=10)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox

    @property
    def foot_y(self):
        """Ground-plane Y position of this character (pivot-corrected foot)."""
        return self.hurtbox.bottom

    def load_assets(self):
        anim_config = load_character_animations('goblin_warrior')
        self.animator = Animator.from_config(anim_config)

    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0:
            return
        self._ensure_health_bar()
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
            self.vel.x = knockback_dir * 1.8
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration
            self.combo_step = 0  # getting hit breaks the combo
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        # Handle death state first
        if self.hp <= 0 or self.animator.state == 'death':
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)

            if not self.dying:
                self.update_animation(dt)
                if self.animator.is_finished():
                    self.dying = True
                    self.death_fade_timer = 0
            else:
                self.death_fade_timer += dt
                if self.death_fade_timer > self.death_fade_delay:
                    fade_progress = (self.death_fade_timer - self.death_fade_delay) / self.death_fade_duration
                    self.alpha = max(0, int(255 * (1.0 - fade_progress)))
                    self._apply_alpha()
                    if self.alpha <= 0:
                        self.kill()
            return

        # Handle hurt timer
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

        # Handle combo attack states
        current_attack = self.animator.state
        if current_attack in ('attack1', 'attack2'):
            # Spawn attack hitbox at the designated hit frame
            if self.animator.is_at_hit_frame() and not self.has_attacked:
                damage = {1: 8, 2: 12}.get(self.combo_step, 8)
                self._spawn_enemy_attack_hitbox(groups, damage)
                self.has_attacked = True

            self.update_animation(dt)
            if self.animator.is_finished():
                # Check if player is still in range for combo continuation
                dist_x = player.hurtbox.centerx - self.hurtbox.centerx
                dist_y = player.hurtbox.bottom - self.hurtbox.bottom
                in_range = abs(dist_x) <= GOBLIN_WARRIOR_ATTACK_RANGE_X and abs(dist_y) <= GOBLIN_WARRIOR_ATTACK_RANGE_Y

                if in_range and self.combo_step < 2:
                    # Chain to next combo step
                    self.combo_step += 1
                    state_name = f'attack{self.combo_step}'
                    self.animator.set_state(state_name, reset=True)
                    self.has_attacked = False
                else:
                    # Combo finished or player moved away
                    self.combo_step = 0
                    self.animator.set_state('idle', reset=False)
                    self.ai_state = 'wait'
                    self.ai_timer = random.randint(500, 1000)
            return

        # AI Behavior State Machine
        self.ai_timer -= dt

        if self.ai_state == 'wait':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
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
            target_x = player.rect.centerx + self.target_offset.x
            target_y = player.rect.bottom + self.target_offset.y

            dist_x = target_x - self.rect.centerx
            dist_y = target_y - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)

            real_dist_x = player.rect.centerx - self.rect.centerx
            real_dist_y = player.rect.bottom - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)

            range_x = GOBLIN_WARRIOR_ATTACK_RANGE_X
            range_y = GOBLIN_WARRIOR_ATTACK_RANGE_Y

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

                if random.random() < 0.005:
                    self.ai_state = 'idle'
                    self.ai_timer = random.randint(1000, 2000)
            else:
                # In range to attack — start combo
                if pygame.time.get_ticks() - self.attack_timer > 1500:
                    self.combo_step = 1
                    self.animator.set_state('attack1', reset=True)
                    self.has_attacked = False
                    self.attack_timer = pygame.time.get_ticks()

        if moving:
            self.animator.set_state('run', reset=False)
        else:
            if self.animator.state not in ('attack1', 'attack2', 'hit', 'death'):
                self.animator.set_state('idle', reset=False)

        # Clamp position
        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))

        self.update_animation(dt)

    def update_animation(self, dt):
        if getattr(self, 'animator', None) is not None:
            self.animator.update(dt)
            pdx_old = getattr(self, 'current_pdx', 0)
            pdy_old = getattr(self, 'current_pdy', 0)
            self.rect.x -= pdx_old
            self.rect.y -= pdy_old

            mid = self.rect.midbottom
            frame = self.animator.get_frame()
            pdx, pdy = self.animator.get_pivot_delta()
            if self.facing == -1:
                frame = pygame.transform.flip(frame, True, False)
                pdx = -pdx
            self.image = frame
            self.rect = self.image.get_rect(midbottom=mid)
            self.rect.x += pdx
            self.rect.y += pdy
            self.current_pdx = pdx
            self.current_pdy = pdy
            self._update_hurtbox()

    def _apply_alpha(self):
        if self.image is not None:
            faded = self.image.copy()
            faded.fill((255, 255, 255, self.alpha), special_flags=pygame.BLEND_RGBA_MULT)
            self.image = faded

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def _spawn_enemy_attack_hitbox(self, groups, damage, w=None, h=None, state=None):
        """Spawn an enemy melee attack hitbox, reading size from metadata when possible."""
        sn = state or getattr(self.animator, 'state', None)
        entry = self.animator.states_config.get(sn, {}) \
            if hasattr(self.animator, 'states_config') else {}
        w = entry.get('hitbox_w', w or 50)
        h = entry.get('hitbox_h', h or 46)
        offset_x = entry.get('hitbox_offset_x', 0)
        offset_y = entry.get('hitbox_offset_y', 0)
        
        pivot_x, pivot_y = self._get_true_pivot()
        
        if self.facing == 1:
            hb_x = pivot_x + offset_x
        else:
            hb_x = pivot_x - offset_x - w
        hb_y = pivot_y - h // 2 + offset_y
        
        hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=damage, duration=100)
        groups['enemy_attacks'].add(hitbox)

    def on_death(self):
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0
        self.combo_step = 0


class GoblinSpearman(pygame.sprite.Sprite, HealthMixin):
    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=40)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.speed = 1.3
        self.facing = -1
        self.attack_timer = 0
        self.vel = pygame.math.Vector2(0, 0)
        self.hurt_timer = 0
        self.ai_state = 'chase'
        self.ai_timer = 0
        self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
        self.has_attacked = False
        # Death fade-out state
        self.dying = False
        self.death_fade_timer = 0
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=28, default_h=96, default_ox=-15)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox

    @property
    def foot_y(self):
        """Ground-plane Y position of this character (pivot-corrected foot)."""
        return self.hurtbox.bottom

    def load_assets(self):
        anim_config = load_character_animations('goblin_spearman')
        self.animator = Animator.from_config(anim_config)

    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0:
            return
        self._ensure_health_bar()
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
            self.vel.x = knockback_dir * 2.0
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        # Handle death state first
        if self.hp <= 0 or self.animator.state == 'death':
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)

            if not self.dying:
                self.update_animation(dt)
                if self.animator.is_finished():
                    self.dying = True
                    self.death_fade_timer = 0
            else:
                self.death_fade_timer += dt
                if self.death_fade_timer > self.death_fade_delay:
                    fade_progress = (self.death_fade_timer - self.death_fade_delay) / self.death_fade_duration
                    self.alpha = max(0, int(255 * (1.0 - fade_progress)))
                    self._apply_alpha()
                    if self.alpha <= 0:
                        self.kill()
            return

        # Handle hurt timer
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

        # Handle attack state
        if self.animator.state == 'attack':
            # Spawn spear at frame 6
            if self.animator.frame_index == 6 and not self.has_attacked:
                spear = Spear(self.rect.centerx, self.rect.centery, player.rect.centerx, player.rect.centery)
                spear.owner = self
                if 'enemy_projectiles' in groups:
                    groups['enemy_projectiles'].add(spear)
                self.has_attacked = True

            self.update_animation(dt)
            if self.animator.is_finished():
                self.animator.set_state('idle', reset=False)
                self.ai_state = 'wait'
                self.ai_timer = random.randint(800, 1500)
            return

        # AI Behavior State Machine
        self.ai_timer -= dt

        if self.ai_state == 'wait':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
                self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
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
            from config import WIDTH
            dx = player.rect.centerx - self.rect.centerx
            dy = player.rect.centery - self.rect.centery
            dist = math.hypot(dx, dy)
            
            in_range = False
            if dist <= WIDTH / 2:
                angle = math.degrees(math.atan2(dy, dx))
                facing_angle = 0 if self.facing == 1 else 180
                diff = (angle - facing_angle + 180) % 360 - 180
                if abs(diff) <= 60:
                    in_range = True

            if not in_range:
                # Move toward player
                target_x = player.rect.centerx + self.target_offset.x
                target_y = player.rect.bottom + self.target_offset.y

                dist_x = target_x - self.rect.centerx
                dist_y = target_y - self.rect.bottom

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

                if random.random() < 0.005:
                    self.ai_state = 'idle'
                    self.ai_timer = random.randint(1000, 2000)
            else:
                # In range to attack
                if pygame.time.get_ticks() - self.attack_timer > 2000:
                    self.animator.set_state('attack', reset=True)
                    self.has_attacked = False
                    self.attack_timer = pygame.time.get_ticks()

        if moving:
            self.animator.set_state('run', reset=False)
        else:
            if self.animator.state not in ('attack', 'hit', 'death'):
                self.animator.set_state('idle', reset=False)

        # Clamp position
        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))

        self.update_animation(dt)

    def update_animation(self, dt):
        if getattr(self, 'animator', None) is not None:
            self.animator.update(dt)
            pdx_old = getattr(self, 'current_pdx', 0)
            pdy_old = getattr(self, 'current_pdy', 0)
            self.rect.x -= pdx_old
            self.rect.y -= pdy_old

            mid = self.rect.midbottom
            frame = self.animator.get_frame()
            pdx, pdy = self.animator.get_pivot_delta()
            if self.facing == -1:
                frame = pygame.transform.flip(frame, True, False)
                pdx = -pdx
            self.image = frame
            self.rect = self.image.get_rect(midbottom=mid)
            self.rect.x += pdx
            self.rect.y += pdy
            self.current_pdx = pdx
            self.current_pdy = pdy
            self._update_hurtbox()

    def _apply_alpha(self):
        if self.image is not None:
            faded = self.image.copy()
            faded.fill((255, 255, 255, self.alpha), special_flags=pygame.BLEND_RGBA_MULT)
            self.image = faded

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def on_death(self):
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0


class GoblinTank(pygame.sprite.Sprite, HealthMixin):
    def __init__(self, pos=(800, 300)):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=250)
        self.load_assets()
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        self.speed = 0.6
        self.facing = -1
        self.attack_timer = 0
        self.vel = pygame.math.Vector2(0, 0)
        self.hurt_timer = 0
        self.ai_state = 'chase'
        self.ai_timer = 0
        self.target_offset = pygame.math.Vector2(random.randint(-40, 40), random.randint(-20, 20))
        self.has_attacked = False
        self.combo_step = 0
        self.jump_dx = 0
        self.jump_dy = 0
        self.jump_exact_x = 0.0
        self.jump_exact_y = 0.0
        # Death fade-out state
        self.dying = False
        self.death_fade_timer = 0
        self.death_fade_delay = DEATH_FADE_DELAY
        self.death_fade_duration = DEATH_FADE_DURATION
        self.alpha = 255
        _hb_w, _hb_h, _hb_ox = _hurtbox_from_config(
            self.animator.states_config if hasattr(self.animator, 'states_config') else {},
            default_w=44, default_h=128, default_ox=10)
        self.hurtbox = pygame.Rect(0, 0, _hb_w, _hb_h)
        self.hurtbox.midbottom = self.rect.midbottom
        self.hurtbox_offset_x = _hb_ox
        # Camera shake state
        self.camera_shake_triggered = False
        self._last_shake_frame = -1
        self.shake_frames = {
            'attack2': {4, 9},
            'death': {3, 6, 9, 14},
            'jump': {2, 10},
            'run': {1, 5, 7},
        }

    @property
    def foot_y(self):
        """Ground-plane Y position of this character (pivot-corrected foot)."""
        return self.hurtbox.bottom

    def load_assets(self):
        anim_config = load_character_animations('goblin_tank')

        # Truncate run to 8 frames: frames 0-7 are the run loop, 8+ is stopping
        if 'run' in anim_config and len(anim_config['run']['frames']) > 8:
            anim_config['run']['frames'] = anim_config['run']['frames'][:8]

        self.animator = Animator.from_config(anim_config)

    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0:
            return
        self._ensure_health_bar()
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.on_death()
        else:
            stun_immune = False
            current_state = self.animator.state if getattr(self, 'animator', None) is not None else None
            
            if current_state in ('jump', 'attack1', 'attack2'):
                stun_immune = True
            elif current_state == 'idle':
                if not is_crit:
                    stun_immune = True
                    
            if stun_immune:
                # Still notify bar even if animation stun is skipped
                if self.health_bar is not None:
                    self.health_bar.notify_damage(self.hp)
                return

            if getattr(self, 'animator', None) is not None:
                self.animator.set_state('hit', reset=True)
            # Knock back away from the damage source
            if source_x is not None:
                knockback_dir = 1 if self.rect.centerx > source_x else -1
            else:
                knockback_dir = -self.facing
            self.vel.x = knockback_dir * 1.0  # very heavy, minimal knockback
            hit_frames = len(self.animator.states['hit'])
            hit_duration = hit_frames * self.animator.durations.get('hit', 100)
            self.hurt_timer = hit_duration
            self.combo_step = 0  # getting hit breaks the combo
        if self.health_bar is not None:
            self.health_bar.notify_damage(self.hp)

    def update(self, dt, player=None, groups=None):
        if player is None or groups is None:
            return

        # Handle death state first
        if self.hp <= 0 or self.animator.state == 'death':
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)

            if not self.dying:
                self.update_animation(dt)
                if self.animator.is_finished():
                    self.dying = True
                    self.death_fade_timer = 0
            else:
                self.death_fade_timer += dt
                if self.death_fade_timer > self.death_fade_delay:
                    fade_progress = (self.death_fade_timer - self.death_fade_delay) / self.death_fade_duration
                    self.alpha = max(0, int(255 * (1.0 - fade_progress)))
                    self._apply_alpha()
                    if self.alpha <= 0:
                        self.kill()
            return

        # Handle hurt timer
        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.rect.x += int(self.vel.x)
            self.vel.x *= 0.85  # heavier, slower decel
            self.rect.left = max(MIN_X, self.rect.left)
            self.rect.right = min(MAX_X, self.rect.right)
            self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))

            if self.hurt_timer <= 0:
                if getattr(self, 'animator', None) is not None:
                    self.animator.set_state('idle', reset=False)
            self.update_animation(dt)
            return

        # Handle attack and jump states
        current_state = self.animator.state
        if current_state == 'jump':
            frame = self.animator.frame_index
            if 3 <= frame <= 9:
                self.jump_exact_x += self.jump_dx * (dt / 16.666)
                self.jump_exact_y += self.jump_dy * (dt / 16.666)
                int_x = int(self.jump_exact_x)
                int_y = int(self.jump_exact_y)
                self.rect.x += int_x
                self.rect.y += int_y
                self.jump_exact_x -= int_x
                self.jump_exact_y -= int_y
            self.update_animation(dt)
            if self.animator.is_finished():
                self.combo_step = 1
                self.animator.set_state('attack1', reset=True)
                self.has_attacked = False
                self.attack_timer = pygame.time.get_ticks()
            return

        if current_state in ('attack1', 'attack2'):
            if current_state == 'attack2':
                frame = self.animator.frame_index
                if 4 <= frame <= 8:
                    self.jump_exact_x += self.jump_dx * (dt / 16.666)
                    self.jump_exact_y += self.jump_dy * (dt / 16.666)
                    int_x = int(self.jump_exact_x)
                    int_y = int(self.jump_exact_y)
                    self.rect.x += int_x
                    self.rect.y += int_y
                    self.jump_exact_x -= int_x
                    self.jump_exact_y -= int_y

            # Spawn attack hitbox at the designated hit frame(s)
            if self.animator.is_at_hit_frame():
                if not self.has_attacked:
                    damage = 25 if current_state == 'attack2' else 15
                    self._spawn_enemy_attack_hitbox(groups, damage)
                    self.has_attacked = True
            else:
                self.has_attacked = False

            self.update_animation(dt)
            if self.animator.is_finished():
                # Check if player is still in range for combo continuation
                dist_x = player.hurtbox.centerx - self.hurtbox.centerx
                dist_y = player.hurtbox.bottom - self.hurtbox.bottom
                # Use base range to determine if we should chain into attack2
                in_range = abs(dist_x) <= GOBLIN_TANK_ATTACK_RANGE_X and abs(dist_y) <= GOBLIN_TANK_ATTACK_RANGE_Y

                if in_range and self.combo_step < 2 and current_state == 'attack1':
                    # Chain to next combo step
                    self.combo_step += 1
                    state_name = f'attack{self.combo_step}'
                    self.animator.set_state(state_name, reset=True)
                    self.has_attacked = False
                    self.jump_dx = 0
                    self.jump_dy = 0
                else:
                    # Combo finished or player moved away
                    self.combo_step = 0
                    self.animator.set_state('idle', reset=False)
                    self.ai_state = 'wait'
                    self.ai_timer = random.randint(1000, 2000)
            return

        # AI Behavior State Machine
        self.ai_timer -= dt

        if self.ai_state == 'wait':
            if self.ai_timer <= 0:
                self.ai_state = 'chase'
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
            target_x = player.rect.centerx + self.target_offset.x
            target_y = player.rect.bottom + self.target_offset.y

            dist_x = target_x - self.rect.centerx
            dist_y = target_y - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)

            real_dist_x = player.rect.centerx - self.rect.centerx
            real_dist_y = player.rect.bottom - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)

            range_x = GOBLIN_TANK_ATTACK_RANGE_X
            range_y = GOBLIN_TANK_ATTACK_RANGE_Y

            is_out_of_range = (real_dist_x**2) / (range_x**2) + (real_dist_y**2) / (range_y**2) > 1
            
            jump_range_x = range_x * 3
            jump_range_y = range_y * 3
            is_within_jump_range = (real_dist_x**2) / (jump_range_x**2) + (real_dist_y**2) / (jump_range_y**2) <= 1

            if is_out_of_range:
                if is_within_jump_range and pygame.time.get_ticks() - self.attack_timer > 3000:
                    choice = random.choice(['jump', 'jump_slam'])
                    self.attack_timer = pygame.time.get_ticks()
                    self.has_attacked = False
                    self.facing = 1 if real_dist_x > 0 else -1
                    self.jump_exact_x = 0.0
                    self.jump_exact_y = 0.0
                    
                    if choice == 'jump':
                        self.animator.set_state('jump', reset=True)
                        self.jump_dx = real_dist_x / 40.0
                        self.jump_dy = real_dist_y / 40.0
                    else:
                        self.combo_step = 2
                        self.animator.set_state('attack2', reset=True)
                        self.jump_dx = real_dist_x / 30.0
                        self.jump_dy = real_dist_y / 30.0
                else:
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

                    if random.random() < 0.005:
                        self.ai_state = 'idle'
                        self.ai_timer = random.randint(1000, 2000)
            else:
                # In range to attack — start combo
                if pygame.time.get_ticks() - self.attack_timer > 2500:
                    self.combo_step = 1
                    self.animator.set_state('attack1', reset=True)
                    self.has_attacked = False
                    self.attack_timer = pygame.time.get_ticks()

        if moving:
            self.animator.set_state('run', reset=False)
        else:
            if self.animator.state not in ('attack1', 'attack2', 'jump', 'hit', 'death'):
                self.animator.set_state('idle', reset=False)

        # Clamp position
        self.rect.left = max(MIN_X, self.rect.left)
        self.rect.right = min(MAX_X, self.rect.right)
        self.rect.bottom = max(MIN_Y, min(MAX_Y, self.rect.bottom))

        self.update_animation(dt)

    def update_animation(self, dt):
        if getattr(self, 'animator', None) is not None:
            self.animator.update(dt)

            # Check for camera shake trigger
            self.camera_shake_triggered = False
            current_state = self.animator.state
            current_frame = self.animator.frame_index
            if current_state in self.shake_frames:
                if current_frame in self.shake_frames[current_state] and current_frame != self._last_shake_frame:
                    self.camera_shake_triggered = True
                    self._last_shake_frame = current_frame
                elif current_frame != self._last_shake_frame:
                    self._last_shake_frame = current_frame

            pdx_old = getattr(self, 'current_pdx', 0)
            pdy_old = getattr(self, 'current_pdy', 0)
            self.rect.x -= pdx_old
            self.rect.y -= pdy_old

            mid = self.rect.midbottom
            frame = self.animator.get_frame()
            pdx, pdy = self.animator.get_pivot_delta()
            if self.facing == -1:
                frame = pygame.transform.flip(frame, True, False)
                pdx = -pdx
            self.image = frame
            self.rect = self.image.get_rect(midbottom=mid)
            self.rect.x += pdx
            self.rect.y += pdy
            self.current_pdx = pdx
            self.current_pdy = pdy
            self._update_hurtbox()

    def _apply_alpha(self):
        if self.image is not None:
            faded = self.image.copy()
            faded.fill((255, 255, 255, self.alpha), special_flags=pygame.BLEND_RGBA_MULT)
            self.image = faded

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)

    def _spawn_enemy_attack_hitbox(self, groups, damage, w=None, h=None, state=None):
        """Spawn an enemy melee attack hitbox, reading size from metadata when possible."""
        sn = state or getattr(self.animator, 'state', None)
        entry = self.animator.states_config.get(sn, {}) \
            if hasattr(self.animator, 'states_config') else {}
        w = entry.get('hitbox_w', w or 70)
        h = entry.get('hitbox_h', h or 60)
        offset_x = entry.get('hitbox_offset_x', 0)
        offset_y = entry.get('hitbox_offset_y', 0)
        
        pivot_x, pivot_y = self._get_true_pivot()
        
        if self.facing == 1:
            hb_x = pivot_x + offset_x
        else:
            hb_x = pivot_x - offset_x - w
        hb_y = pivot_y - h // 2 + offset_y
        
        hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=damage, duration=100)
        groups['enemy_attacks'].add(hitbox)

    def on_death(self):
        if getattr(self, 'animator', None) is not None:
            self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0
        self.combo_step = 0



class FatCultist(pygame.sprite.Sprite, HealthMixin):
    """Miniboss for Phase 3. Slow movement, high HP, 2 attack animations."""
    def __init__(self, pos):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=500)
        
        self.animator = Animator.from_config(load_character_animations('fat_cultist'))
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        
        self.hurtbox_w, self.hurtbox_h, self.hurtbox_offset_x = _hurtbox_from_config(self.animator.states_config)
        self.hurtbox = pygame.Rect(0, 0, self.hurtbox_w, self.hurtbox_h)
        
        self.vel = pygame.math.Vector2(0, 0)
        self.speed = 1.0
        self.facing = -1
        
        self._update_hurtbox()
        
        self.hurt_timer = 0
        self.has_attacked = False
        
        # State machine
        self.is_attacking = False
        self.combo_step = 0

    @property
    def foot_y(self):
        return self.hurtbox.bottom

    def _get_true_pivot(self):
        if not hasattr(self, 'rect'): return (0, 0)
        foot_x = self.rect.midbottom[0] - getattr(self, 'current_pdx', 0)
        foot_y = self.rect.midbottom[1] - getattr(self, 'current_pdy', 0)
        animator = getattr(self, 'animator', None)
        if not animator: return (foot_x, foot_y)
        sn = getattr(animator, 'state', None)
        entry = getattr(animator, 'states_config', {}).get(sn, {})
        idle_mb_ox = entry.get('idle_mb_ox', 0)
        idle_mb_oy = entry.get('idle_mb_oy', 0)
        if getattr(self, 'facing', 1) == 1:
            return foot_x + idle_mb_ox, foot_y + idle_mb_oy
        else:
            return foot_x - idle_mb_ox, foot_y + idle_mb_oy

    def update(self, dt, player, groups):
        if self.hp <= 0:
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)
            self.animator.update(dt)
            if self.animator.is_finished():
                self.kill()
            self._update_hurtbox()
            return
            
        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.animator.update(dt)
            if self.animator.is_finished():
                self.hurt_timer = 0
                self.animator.set_state('idle')
        else:
            self._update_ai(dt, player, groups)
            self.animator.update(dt)
            
        self.rect.x += self.vel.x
        self.rect.y += self.vel.y
        self._update_visuals()

    def _update_ai(self, dt, player, groups):
        target_x = player.hurtbox.centerx
        target_y = player.foot_y
        dist_x = target_x - self.rect.centerx
        dist_y = target_y - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)
        real_dist_x = player.hurtbox.centerx - self.rect.centerx
        real_dist_y = player.rect.bottom - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)
        
        if not self.is_attacking:
            self.facing = 1 if dist_x > 0 else -1
            
            in_range_attack1 = abs(dist_x) <= FAT_CULTIST_ATTACK_RANGE_X and abs(dist_y) <= FAT_CULTIST_ATTACK_RANGE_Y
            in_range_attack2 = abs(dist_x) <= FAT_CULTIST_ATTACK_2_RANGE_X and abs(dist_y) <= FAT_CULTIST_ATTACK_2_RANGE_Y
            
            if in_range_attack1 or in_range_attack2:
                self.vel.x = 0
                self.vel.y = 0
                self.is_attacking = True
                self.has_attacked = False
                
                # Randomly pick attack based on range
                if in_range_attack1 and in_range_attack2:
                    if random.random() < 0.5:
                        self.animator.set_state('attack1', reset=True)
                        self.combo_step = 1
                    else:
                        self.animator.set_state('attack2', reset=True)
                        self.combo_step = 2
                elif in_range_attack2:
                    self.animator.set_state('attack2', reset=True)
                    self.combo_step = 2
            else:
                self.animator.set_state('run')
                dist = math.hypot(dist_x, dist_y)
                if dist > 0:
                    self.vel.x = (dist_x / dist) * self.speed
                    self.vel.y = (dist_y / dist) * self.speed
        else:
            self.vel.x = 0
            self.vel.y = 0
            
            sn = self.animator.state
            entry = self.animator.states_config.get(sn, {})
            hit_frames = entry.get('hit_frame', [6])
            if not isinstance(hit_frames, list):
                hit_frames = [hit_frames]
                
            if self.animator.frame_index in hit_frames and not self.has_attacked:
                damage = 35 if self.combo_step == 2 else 20
                self._spawn_enemy_attack_hitbox(groups, damage)
                self.has_attacked = True
                
            if self.animator.frame_index not in hit_frames:
                self.has_attacked = False
                
            if self.animator.is_finished():
                self.is_attacking = False
                self.animator.set_state('idle')

    def _spawn_enemy_attack_hitbox(self, groups, damage):
        sn = self.animator.state
        entry = self.animator.states_config.get(sn, {})
        w = entry.get('hitbox_w', 60)
        h = entry.get('hitbox_h', 40)
        offset_x = entry.get('hitbox_offset_x', 0)
        offset_y = entry.get('hitbox_offset_y', 0)
        
        pivot_x, pivot_y = self._get_true_pivot()
        if self.facing == 1: hb_x = pivot_x + offset_x
        else: hb_x = pivot_x - offset_x - w
        hb_y = pivot_y - h // 2 + offset_y
        
        hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=damage, duration=100)
        groups['enemy_attacks'].add(hitbox)

    def _update_visuals(self):
        pdx_old = getattr(self, 'current_pdx', 0)
        pdy_old = getattr(self, 'current_pdy', 0)
        self.rect.x -= pdx_old
        self.rect.y -= pdy_old
        mid = self.rect.midbottom
        frame = self.animator.get_frame()
        pdx, pdy = self.animator.get_pivot_delta()
        if self.facing == -1:
            frame = pygame.transform.flip(frame, True, False)
            pdx = -pdx
        self.image = frame
        self.rect = self.image.get_rect(midbottom=mid)
        self.rect.x += pdx
        self.rect.y += pdy
        self.current_pdx = pdx
        self.current_pdy = pdy
        self._update_hurtbox()

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)
        
    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0: return
        super().take_damage(amount, source_x, is_crit)
        if self.hp > 0 and not self.is_attacking:
            self.animator.set_state('hit', reset=True)
            self.hurt_timer = self.animator.states_config['hit']['duration'] * len(self.animator.states_config['hit']['frames'])
            self.vel.x = 0
            self.vel.y = 0

    def on_death(self):
        if self.animator: self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0


class DeathBringerSpell(pygame.sprite.Sprite):
    def __init__(self, x, y, damage, groups):
        pygame.sprite.Sprite.__init__(self)
        self.groups = groups
        self.animator = Animator.from_config(load_character_animations('death_bringer_spell'))
        self.animator.set_state('spell')
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(center=(x, y))
        self.damage = damage
        self.has_hit = False
        
    def update(self, dt):
        self.animator.update(dt)
        self.image = self.animator.get_frame()
        
        sn = self.animator.state
        entry = self.animator.states_config.get(sn, {})
        hit_frame = entry.get('hit_frame', 4)
        
        if self.animator.frame_index == hit_frame and not self.has_hit:
            self.has_hit = True
            w = entry.get('hitbox_w', 80)
            h = entry.get('hitbox_h', 120)
            ox = entry.get('hitbox_offset_x', -40)
            oy = entry.get('hitbox_offset_y', -100)
            
            # Since this effect has no facing, the hitbox is just applied at the center of the effect
            hb_x = self.rect.centerx + ox
            hb_y = self.rect.centery + oy
            
            # We must pass an owner for knockback. The spell itself isn't a character, so we pass self (which doesn't have foot_y or hurtbox).
            # We'll mock it for the collision system.
            self.foot_y = self.rect.bottom
            self.owner = self
            hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=self.damage, duration=100)
            self.groups['enemy_attacks'].add(hitbox)
            
        if self.animator.is_finished():
            self.kill()


class DeathBringer(pygame.sprite.Sprite, HealthMixin):
    """Final Boss for Phase 3. Has standard melee attack, and a spell attack that spawns a spell effect."""
    def __init__(self, pos):
        pygame.sprite.Sprite.__init__(self)
        HealthMixin.__init__(self, max_hp=1000)
        
        self.animator = Animator.from_config(load_character_animations('bringer_of_death'))
        self.image = self.animator.get_frame()
        self.rect = self.image.get_rect(midbottom=pos)
        
        self.hurtbox_w, self.hurtbox_h, self.hurtbox_offset_x = _hurtbox_from_config(self.animator.states_config)
        self.hurtbox = pygame.Rect(0, 0, self.hurtbox_w, self.hurtbox_h)
        
        self.vel = pygame.math.Vector2(0, 0)
        self.speed = 1.2
        self.facing = -1
        
        self._update_hurtbox()
        
        self.hurt_timer = 0
        self.has_attacked = False
        
        self.is_attacking = False
        self.last_spell_time = pygame.time.get_ticks() - DEATH_BRINGER_SPELL_COOLDOWN

    @property
    def foot_y(self):
        return self.hurtbox.bottom

    def _get_true_pivot(self):
        if not hasattr(self, 'rect'): return (0, 0)
        foot_x = self.rect.midbottom[0] - getattr(self, 'current_pdx', 0)
        foot_y = self.rect.midbottom[1] - getattr(self, 'current_pdy', 0)
        animator = getattr(self, 'animator', None)
        if not animator: return (foot_x, foot_y)
        sn = getattr(animator, 'state', None)
        entry = getattr(animator, 'states_config', {}).get(sn, {})
        idle_mb_ox = entry.get('idle_mb_ox', 0)
        idle_mb_oy = entry.get('idle_mb_oy', 0)
        if getattr(self, 'facing', 1) == 1:
            return foot_x + idle_mb_ox, foot_y + idle_mb_oy
        else:
            return foot_x - idle_mb_ox, foot_y + idle_mb_oy

    def update(self, dt, player, groups):
        if self.hp <= 0:
            if self.animator.state != 'death':
                self.animator.set_state('death', reset=True)
            self.animator.update(dt)
            if self.animator.is_finished():
                self.kill()
            self._update_hurtbox()
            return
            
        if self.hurt_timer > 0:
            self.hurt_timer -= dt
            self.animator.update(dt)
            if self.animator.is_finished():
                self.hurt_timer = 0
                self.animator.set_state('idle')
        else:
            self._update_ai(dt, player, groups)
            self.animator.update(dt)
            
        self.rect.x += self.vel.x
        self.rect.y += self.vel.y
        self._update_visuals()

    def _update_ai(self, dt, player, groups):
        target_x = player.hurtbox.centerx
        target_y = player.foot_y
        dist_x = target_x - self.rect.centerx
        dist_y = target_y - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)
        real_dist_x = player.hurtbox.centerx - self.rect.centerx
        real_dist_y = player.rect.bottom - (self.rect.bottom + ENEMY_ATTACK_OFFSET_Y)
        
        now = pygame.time.get_ticks()
        can_spell = (now - self.last_spell_time > DEATH_BRINGER_SPELL_COOLDOWN)
        
        if not self.is_attacking:
            self.facing = 1 if dist_x > 0 else -1
            
            in_melee = abs(dist_x) <= DEATH_BRINGER_ATTACK_RANGE_X and abs(dist_y) <= DEATH_BRINGER_ATTACK_RANGE_Y
            in_spell_range = abs(dist_x) <= DEATH_BRINGER_CAST_RANGE_X and abs(dist_y) <= DEATH_BRINGER_CAST_RANGE_Y
            
            if can_spell and in_spell_range:
                self.vel.x = 0
                self.vel.y = 0
                self.is_attacking = True
                self.has_attacked = False
                self.animator.set_state('cast', reset=True)
                self.last_spell_time = now
            elif in_melee:
                self.vel.x = 0
                self.vel.y = 0
                self.is_attacking = True
                self.has_attacked = False
                self.animator.set_state('attack', reset=True)
            else:
                self.animator.set_state('run')
                dist = math.hypot(dist_x, dist_y)
                if dist > 0:
                    self.vel.x = (dist_x / dist) * self.speed
                    self.vel.y = (dist_y / dist) * self.speed
        else:
            self.vel.x = 0
            self.vel.y = 0
            
            if self.animator.state == 'attack':
                hit_frame = self.animator.states_config.get('attack', {}).get('hit_frame', 7)
                if self.animator.frame_index == hit_frame and not self.has_attacked:
                    self._spawn_enemy_attack_hitbox(groups, damage=40)
                    self.has_attacked = True
                    
            elif self.animator.state == 'cast':
                if self.animator.frame_index == 3 and not self.has_attacked:
                    # Spawn the spell effect right on top of the player's feet
                    spell = DeathBringerSpell(player.hurtbox.centerx, player.foot_y, damage=50, groups=groups)
                    groups['effects'].add(spell)
                    self.has_attacked = True
                    
            if self.animator.is_finished():
                self.is_attacking = False
                self.animator.set_state('idle')

    def _spawn_enemy_attack_hitbox(self, groups, damage):
        sn = self.animator.state
        entry = self.animator.states_config.get(sn, {})
        w = entry.get('hitbox_w', 80)
        h = entry.get('hitbox_h', 60)
        offset_x = entry.get('hitbox_offset_x', 0)
        offset_y = entry.get('hitbox_offset_y', 0)
        
        pivot_x, pivot_y = self._get_true_pivot()
        if self.facing == 1: hb_x = pivot_x + offset_x
        else: hb_x = pivot_x - offset_x - w
        hb_y = pivot_y - h // 2 + offset_y
        
        hitbox = AttackHitbox(self, (hb_x, hb_y, w, h), damage=damage, duration=100)
        groups['enemy_attacks'].add(hitbox)

    def _update_visuals(self):
        pdx_old = getattr(self, 'current_pdx', 0)
        pdy_old = getattr(self, 'current_pdy', 0)
        self.rect.x -= pdx_old
        self.rect.y -= pdy_old
        mid = self.rect.midbottom
        frame = self.animator.get_frame()
        pdx, pdy = self.animator.get_pivot_delta()
        if self.facing == -1:
            frame = pygame.transform.flip(frame, True, False)
            pdx = -pdx
        self.image = frame
        self.rect = self.image.get_rect(midbottom=mid)
        self.rect.x += pdx
        self.rect.y += pdy
        self.current_pdx = pdx
        self.current_pdy = pdy
        self._update_hurtbox()

    def _update_hurtbox(self):
        pivot_x, pivot_y = self._get_true_pivot()
        self.hurtbox.midbottom = (pivot_x + self.hurtbox_offset_x * self.facing, pivot_y)
        
    def take_damage(self, amount, source_x=None, is_crit=False):
        if self.hp <= 0: return
        super().take_damage(amount, source_x, is_crit)
        # Boss does not flinch to normal attacks while attacking, only flinches in idle/run
        if self.hp > 0 and not self.is_attacking:
            self.animator.set_state('hit', reset=True)
            self.hurt_timer = self.animator.states_config['hit']['duration'] * len(self.animator.states_config['hit']['frames'])
            self.vel.x = 0
            self.vel.y = 0

    def on_death(self):
        if self.animator: self.animator.set_state('death', reset=True)
        self.vel.x = 0
        self.vel.y = 0
        self.hurt_timer = 0

class HealthPotion(pygame.sprite.Sprite):
    def __init__(self, x, y, heal_amount=30, lifetime=10000):
        super().__init__()
        self.heal_amount = heal_amount
        self.lifetime = lifetime
        self.spawn_time = pygame.time.get_ticks()

        # Load image
        try:
            raw_img = pygame.image.load("assets/items/potions/blue.png").convert_alpha()
            self.image = pygame.transform.scale(raw_img, (24,24))
        except Exception:
            self.image = pygame.Surface((20,24))
            self.image.fill((50,255,50))

        self.rect = self.image.get_rect(midbottom=(x,y))
        self.base_y = float(self.rect.y)
        self.float_timer = 0

    @property
    def foot_y(self):
        return self.rect.bottom
    
    def update(self, dt):
        # Auto destroy
        if pygame.time.get_ticks() - self.spawn_time > self.lifetime:
            self.kill()
            return

        # Floating effects
        self.float_timer += dt * 0.005
        self.rect.y = int(self.base_y + math.sin(self.float_timer) * 5)


class AbilityVial(pygame.sprite.Sprite):
    """Green Poison Vial dropped by enemies; grants one ability point."""

    def __init__(self, x, y, lifetime=15000):
        super().__init__()
        self.lifetime = lifetime
        self.spawn_time = pygame.time.get_ticks()
        try:
            raw_img = pygame.image.load("assets/items/potions/green.png").convert_alpha()
            self.image = pygame.transform.scale(raw_img, (26, 26))
        except Exception:
            self.image = pygame.Surface((22, 26), pygame.SRCALPHA)
            self.image.fill((80, 230, 90, 230))

        self.rect = self.image.get_rect(midbottom=(x, y))
        self.base_y = float(self.rect.y)
        self.float_timer = 0

    @property
    def foot_y(self):
        return self.rect.bottom

    def update(self, dt):
        if pygame.time.get_ticks() - self.spawn_time > self.lifetime:
            self.kill()
            return
        self.float_timer += dt * 0.005
        self.rect.y = int(self.base_y + math.sin(self.float_timer) * 7)


class BerserkVial(pygame.sprite.Sprite):
    """Red pickup that temporarily increases damage at an armor cost."""

    def __init__(self, x, y, lifetime=12000):
        super().__init__()
        self.lifetime = lifetime
        self.spawn_time = pygame.time.get_ticks()
        try:
            raw_img = pygame.image.load("assets/items/potions/red.png").convert_alpha()
            self.image = pygame.transform.scale(raw_img, (26, 26))
        except Exception:
            self.image = pygame.Surface((22, 26), pygame.SRCALPHA)
            self.image.fill((245, 75, 65, 230))

        self.rect = self.image.get_rect(midbottom=(x, y))
        self.base_y = float(self.rect.y)
        self.float_timer = 0

    @property
    def foot_y(self):
        return self.rect.bottom

    def update(self, dt):
        if pygame.time.get_ticks() - self.spawn_time > self.lifetime:
            self.kill()
            return
        self.float_timer += dt * 0.006
        self.rect.y = int(self.base_y + math.sin(self.float_timer) * 7)


class SkillIcon(pygame.sprite.Sprite):
    """Skill icon that drops from enemies when they die.
    Can be picked up by the player to add to their skill inventory."""
    
    SKILL_TYPES = {
        'fire': 'assets/skills/icons/fire.png',
        'water_ball': 'assets/skills/icons/water_ball.png',
        'ice': 'assets/skills/icons/water_ball.png',
        'wind': 'assets/skills/icons/wind.png',
        'holy': 'assets/skills/icons/holy.png',
        'light': 'assets/skills/icons/light.png',
        'dark': 'assets/skills/icons/dark.png',
        'smoke': 'assets/skills/icons/smoke.png',
        'wood': 'assets/skills/icons/wood.png',
        'earth': 'assets/skills/icons/earth.png',
        'acid': 'assets/skills/icons/acid.png',
        'shield': 'assets/skills/icons/shield.png',
        'thunder': 'assets/skills/icons/thunder.png',
        'water_blast': 'assets/skills/icons/water_blast.png',
    }
    
    def __init__(self, x, y, skill_type='fire', lifetime=15000):
        super().__init__()
        if skill_type == 'ice':
            skill_type = 'water_ball'
        self.skill_type = skill_type
        self.lifetime = lifetime
        self.spawn_time = pygame.time.get_ticks()
        
        # Load image
        try:
            icon_path = self.SKILL_TYPES.get(skill_type, self.SKILL_TYPES['fire'])
            raw_img = pygame.image.load(icon_path).convert_alpha()
            self.image = pygame.transform.scale(raw_img, (32, 32))
        except Exception:
            self.image = pygame.Surface((32, 32), pygame.SRCALPHA)
            self.image.fill((255, 100, 100, 200))
        
        self.rect = self.image.get_rect(midbottom=(x, y))
        self.base_y = float(self.rect.y)
        self.float_timer = 0
        self.rotation = 0
    
    @property
    def foot_y(self):
        return self.rect.bottom
    
    def update(self, dt):
        # Auto destroy
        if pygame.time.get_ticks() - self.spawn_time > self.lifetime:
            self.kill()
            return
        
        # Floating and rotation effects
        self.float_timer += dt * 0.005
        self.rect.y = int(self.base_y + math.sin(self.float_timer) * 8)
        self.rotation = (self.rotation + dt * 0.3) % 360
        
