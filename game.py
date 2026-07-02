import pygame
import sys
import math
import random
from config import (WIDTH, HEIGHT, FPS, MAP_IMAGE, MIN_Y, MAX_Y,
                     CRIT_CHANCE, CRIT_MULTIPLIER,
                     CAMERA_SHAKE_INTENSITY, CAMERA_SHAKE_DURATION)
from entities import (Knight, Archer, Lizardman, Cyclop, Kobold, Fireworm, DamageNumber,
                       GoblinWarrior, GoblinSpearman, GoblinTank,
                       FatCultist, DeathBringer,
                       DashSmoke, UltimateEffect, KnightUltimateShockwave, BloodVFX, HitVFX,
                       HealthPotion, IcePotion, FirePotion, PoisonPotion)


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Beat-em-up Test")
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "SELECT"
        self.DEBUG_DRAW = False # Set to True to see hitboxes and hurtboxes
        self.selected_hero = 'knight'
        self.selected_phase = 1

        # Camera shake state
        self.camera_offset = [0, 0]
        self.shake_timer = 0
        self.shake_intensity = 0

        # Map initialized dynamically in load()
        self.map = pygame.Surface((WIDTH, HEIGHT))

        # Shadow sprite – drawn beneath every entity each frame
        import os as _os
        _shadow_path = _os.path.join(_os.path.dirname(__file__), 'assets', 'shadow.png')
        try:
            self._shadow_src = pygame.image.load(_shadow_path).convert_alpha()
        except Exception:
            # Fallback: simple dark ellipse if asset is missing
            self._shadow_src = pygame.Surface((64, 16), pygame.SRCALPHA)
            pygame.draw.ellipse(self._shadow_src, (0, 0, 0, 80), self._shadow_src.get_rect())
        self._shadow_cache: dict = {}  # width → scaled surface

        self.knight_preview = Knight(pos=(WIDTH//3, HEIGHT//2 + 50))
        self.archer_preview = Archer(pos=(2*WIDTH//3, HEIGHT//2 + 50))

    def load(self):
        # sprite groups
        self.all_sprites = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.potions = pygame.sprite.Group()
        self.attacks = pygame.sprite.Group()
        self.arrows = pygame.sprite.Group()
        self.enemy_projectiles = pygame.sprite.Group()
        self.enemy_attacks = pygame.sprite.Group()
        self.damage_numbers = pygame.sprite.Group()
        self.effects = pygame.sprite.Group()       # DashSmoke, UltimateEffect visuals
        self.ultimate_beams = pygame.sprite.Group() # UltimateEffect collision set
        self.knight_shockwaves = pygame.sprite.Group()  # KnightUltimateShockwave collision set

        self.groups = {
            'all': self.all_sprites,
            'enemies': self.enemies,
            'potions': self.potions,
            'attacks': self.attacks,
            'arrows': self.arrows,
            'enemy_projectiles': self.enemy_projectiles,
            'enemy_attacks': self.enemy_attacks,
            'damage_numbers': self.damage_numbers,
            'effects': self.effects,
            'ultimate_beams': self.ultimate_beams,
            'knight_shockwaves': self.knight_shockwaves,
        }

        # Dynamically load map depending on phase
        map_files = {
            1: "assets/maps/map1.jpeg",
            2: "assets/maps/map2.jpg",  # Might also be map2.png, but testing confirmed map2.jpg exists
            3: "assets/maps/map3.jpg"   # Might also be map3.png, but testing confirmed map3.jpg exists
        }
        try:
            self.map = pygame.image.load(map_files.get(self.selected_phase, MAP_IMAGE)).convert()
        except Exception as e:
            print(f"Failed to load map for phase {self.selected_phase}: {e}")
            self.map = pygame.Surface((WIDTH, HEIGHT))
            self.map.fill((50, 150, 50))

        # Two-player co-op setup
        self.players = [
            Knight(pos=(WIDTH//3, HEIGHT-100)),
            Archer(pos=(2*WIDTH//3, HEIGHT-100)),
        ]
        self.player = self.players[0]
        for player in self.players:
            self.all_sprites.add(player)

        # spawn timer
        self.spawn_event = pygame.USEREVENT + 1
        pygame.time.set_timer(self.spawn_event, 3500)

        # Boss spawn tracking
        self.phase_start_time = pygame.time.get_ticks()
        self.boss_spawned = False
        self.miniboss_spawned = False
        self.miniboss_defeated = False

        # Reset camera shake
        self.camera_offset = [0, 0]
        self.shake_timer = 0
        self.shake_intensity = 0

    def spawn_enemy(self):
        side = random.choice(['left', 'right'])
        y = random.randint(MIN_Y + 50, MAX_Y - 30)
        x = -40 if side == 'left' else WIDTH + 40

        if self.selected_phase == 1:
            # Phase 1: 60% goblin warrior, 40% goblin spearman
            if random.random() < 0.6:
                enemy = GoblinWarrior(pos=(x, y))
            else:
                enemy = GoblinSpearman(pos=(x, y))
        elif self.selected_phase == 2:
            # Phase 2: 40% Lizardman, 30% Kobold, 20% Fireworm, 10% Cyclop
            rand = random.random()
            if rand < 0.4:
                enemy = Lizardman(pos=(x, y))
            elif rand < 0.7:
                enemy = Kobold(pos=(x, y))
            elif rand < 0.9:
                enemy = Fireworm(pos=(x, y))
            else:
                enemy = Cyclop(pos=(x, y))
        else:
            # Phase 3: Handled in update loop manually
            return

        self.enemies.add(enemy)
        self.all_sprites.add(enemy)

    def spawn_miniboss(self):
        """Spawn the phase's miniboss from the right side."""
        y = (MIN_Y + MAX_Y) // 2
        x = WIDTH + 60
        boss = FatCultist(pos=(x, y))
        self.enemies.add(boss)
        self.all_sprites.add(boss)
        self.miniboss_spawned = True

    def spawn_boss(self):
        """Spawn the phase's boss from the right side."""
        y = (MIN_Y + MAX_Y) // 2  # center of the playable area
        x = WIDTH + 60
        if self.selected_phase == 1:
            boss = GoblinTank(pos=(x, y))
        elif self.selected_phase == 3:
            boss = DeathBringer(pos=(x, y))
        else:
            return  # No boss for phase 2 yet

        self.enemies.add(boss)
        self.all_sprites.add(boss)
        self.boss_spawned = True

    def trigger_camera_shake(self, intensity=None):
        """Start a camera shake effect."""
        self.shake_intensity = intensity or CAMERA_SHAKE_INTENSITY
        self.shake_timer = CAMERA_SHAKE_DURATION

    def update_camera_shake(self, dt):
        """Update camera shake offset, decaying over time."""
        if self.shake_timer > 0:
            self.shake_timer -= dt
            # Intensity decays linearly
            progress = max(0, self.shake_timer / CAMERA_SHAKE_DURATION)
            current_intensity = int(self.shake_intensity * progress)
            if current_intensity > 0:
                self.camera_offset[0] = random.randint(-current_intensity, current_intensity)
                self.camera_offset[1] = random.randint(-current_intensity, current_intensity)
            else:
                self.camera_offset = [0, 0]
        else:
            self.camera_offset = [0, 0]

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)
            if self.state == "SELECT":
                self.events_select()
                self.update_select(dt)
                self.draw_select()
            elif self.state == "PHASE_SELECT":
                self.events_phase_select()
                self.draw_phase_select()
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
                if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_1, pygame.K_2, pygame.K_3):
                    self.state = "PHASE_SELECT"

    def update_select(self, dt):
        self.knight_preview.update(dt, keys=None, groups=None)
        self.archer_preview.update(dt, keys=None, groups=None)

    def draw_select(self):
        self.screen.blit(self.map, (0, 0))

        font_title = pygame.font.SysFont('Arial', 48, bold=True)
        title = font_title.render("Co-op Beat'em Up", True, (255, 255, 255))
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 100)))

        font_sub = pygame.font.SysFont('Arial', 28)
        font_small = pygame.font.SysFont('Arial', 22)

        panel = pygame.Surface((700, 260), pygame.SRCALPHA)
        panel.fill((20, 20, 25, 220))
        self.screen.blit(panel, (WIDTH // 2 - 350, HEIGHT // 2 - 100))

        player1 = font_sub.render("Player 1", True, (120, 220, 255))
        self.screen.blit(player1, player1.get_rect(center=(WIDTH // 2 - 180, HEIGHT // 2 - 40)))
        p1_lines = [
            "Move: A / S / D / W",
            "Attack: J",
            "Defend: K",
            "Ultimate: L"
        ]
        for idx, line in enumerate(p1_lines):
            text = font_small.render(line, True, (240, 240, 240))
            self.screen.blit(text, text.get_rect(center=(WIDTH // 2 - 180, HEIGHT // 2 + 10 + idx * 28)))

        player2 = font_sub.render("Player 2", True, (255, 190, 90))
        self.screen.blit(player2, player2.get_rect(center=(WIDTH // 2 + 180, HEIGHT // 2 - 40)))
        p2_lines = [
            "Move: Arrow keys",
            "Attack: NumPad 1 / 2",
            "Dash: NumPad 3 / 4",
            "Ultimate: NumPad 5 / 6"
        ]
        for idx, line in enumerate(p2_lines):
            text = font_small.render(line, True, (240, 240, 240))
            self.screen.blit(text, text.get_rect(center=(WIDTH // 2 + 180, HEIGHT // 2 + 10 + idx * 28)))

        hint = font_small.render("Press Enter or Space to choose a phase", True, (180, 255, 180))
        self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 120)))

        pygame.display.flip()

    # ── Phase Selection ──────────────────────────────────────────────

    def events_phase_select(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    self.selected_phase = 1
                    self.state = "PLAY"
                    self.load()
                elif event.key == pygame.K_2:
                    self.selected_phase = 2
                    self.state = "PLAY"
                    self.load()
                elif event.key == pygame.K_3:
                    self.selected_phase = 3
                    self.state = "PLAY"
                    self.load()
                elif event.key == pygame.K_ESCAPE:
                    self.state = "SELECT"

    def draw_phase_select(self):
        self.screen.blit(self.map, (0, 0))

        # Semi-transparent overlay for readability
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        self.screen.blit(overlay, (0, 0))

        font_title = pygame.font.SysFont('Arial', 48, bold=True)
        title = font_title.render("Select Phase", True, (255, 255, 255))
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 100)))

        font_sub = pygame.font.SysFont('Arial', 28)

        # Phase 1 description
        text_p1 = font_sub.render("Press 1 - Goblin Invasion", True, (150, 255, 150))
        desc_p1 = font_sub.render("Goblin Warriors, Spearmen & Tank Boss", True, (200, 200, 200))
        self.screen.blit(text_p1, text_p1.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 80)))
        self.screen.blit(desc_p1, desc_p1.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40)))

        # Phase 2 description
        text_p2 = font_sub.render("Press 2 - The Menagerie", True, (255, 220, 150))
        desc_p2 = font_sub.render("Lizardmen, Kobolds, Fireworms & Cyclopes", True, (200, 200, 200))
        self.screen.blit(text_p2, text_p2.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20)))
        self.screen.blit(desc_p2, desc_p2.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 60)))

        # Phase 3 description
        text_p3 = font_sub.render("Press 3 - The Cult", True, (255, 150, 150))
        desc_p3 = font_sub.render("Fat Cultists & Death Bringer Boss", True, (200, 200, 200))
        self.screen.blit(text_p3, text_p3.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 120)))
        self.screen.blit(desc_p3, desc_p3.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 160)))

        # Back hint
        font_hint = pygame.font.SysFont('Arial', 22)
        hint = font_hint.render("ESC to go back", True, (180, 180, 180))
        self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 60)))

        pygame.display.flip()

    # ── Main Gameplay ────────────────────────────────────────────────

    def events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == self.spawn_event:
                if any(player.hp > 0 for player in self.players):
                    self.spawn_enemy()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r and all(player.hp <= 0 for player in self.players):
                    self.state = "SELECT"

    def update(self, dt):
        keys = pygame.key.get_pressed()
        for entity in list(self.players) + list(self.enemies):
            if hasattr(entity, 'update_debuffs'):
                entity.update_debuffs(dt)
        # update players
        for player in self.players:
            player.update(dt, keys, self.groups)

        # update enemies
        for e in list(self.enemies):
            living_players = [p for p in self.players if p.hp > 0]
            if not living_players:
                continue
            target = min(
                living_players,
                key=lambda p: abs(p.rect.centerx - e.rect.centerx)
            )
            e.update(dt, target, self.groups)

        # update enemy health bars (centralised so they tick every frame,
        # even when an enemy is in a hurt / attack / death state).
        for e in self.enemies:
            if getattr(e, 'health_bar', None) is not None:
                e.health_bar.update(dt)

        # update attacks
        self.attacks.update(dt)
        self.enemy_attacks.update(dt)
        self.arrows.update(dt)
        self.enemy_projectiles.update(dt)
        self.damage_numbers.update(dt)
        self.effects.update(dt)
        self.knight_shockwaves.update(dt)
        self.potions.update(dt)

        # Boss spawn logic
        if self.selected_phase == 1 and not self.boss_spawned:
            elapsed = pygame.time.get_ticks() - self.phase_start_time
            if elapsed >= 10000 and any(player.hp > 0 for player in self.players):
                self.spawn_boss()
        elif self.selected_phase == 3:
            if not self.miniboss_spawned:
                # Spawn miniboss slightly after phase starts
                elapsed = pygame.time.get_ticks() - self.phase_start_time
                if elapsed >= 1000 and any(player.hp > 0 for player in self.players):
                    self.spawn_miniboss()
            elif not self.miniboss_defeated:
                if not any(isinstance(e, FatCultist) and e.hp > 0 for e in self.enemies):
                    self.miniboss_defeated = True
                    self.phase_start_time = pygame.time.get_ticks()
            elif not self.boss_spawned:
                elapsed = pygame.time.get_ticks() - self.phase_start_time
                if elapsed >= 3000 and any(player.hp > 0 for player in self.players):
                    self.spawn_boss()

        # Check for camera shake triggers from GoblinTank entities
        for e in self.enemies:
            if isinstance(e, GoblinTank) and getattr(e, 'camera_shake_triggered', False):
                self.trigger_camera_shake()
                e.camera_shake_triggered = False

        # Update camera shake
        self.update_camera_shake(dt)

        # ── Collision Resolution (Hitbox → Hurtbox) ───────────────────

        # 1. Player Attack Hitbox vs Enemy Hurtbox
        for hb in list(self.attacks):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                if id(enemy) in hb.already_hit_targets:
                    continue
                # Phase 1 – Vertical depth filter (melee)
                if math.fabs(hb.owner.foot_y - enemy.foot_y) > 50:
                    continue
                # Phase 2 – 2D AABB collision
                if hb.rect.colliderect(enemy.hurtbox):
                    hb.already_hit_targets.add(id(enemy))
                    is_crit = random.random() < CRIT_CHANCE
                    final_damage = int(hb.damage * CRIT_MULTIPLIER) if is_crit else hb.damage
                    old_hp = enemy.hp
                    enemy.take_damage(final_damage, source_x=hb.owner.rect.centerx, is_crit=is_crit)
                    if hasattr(hb.owner, 'attack_buff'):
                        if hb.owner.attack_buff == 'slow':
                            enemy.apply_debuff('slow', 3000) # Làm chậm 3 giây
                        elif hb.owner.attack_buff == 'burn':
                            enemy.apply_debuff('burn', 4000) # Thiêu đốt 4 giây
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        
                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)

        # 2. Arrow vs Enemy Hurtbox
        for arrow in list(self.arrows):
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                # Phase 1 - Vertical depth filter (projectile)
                if math.fabs(arrow.floor_y - enemy.foot_y) > 50:
                    continue
                # Phase 2 - 2D AABB collision
                if arrow.rect.colliderect(enemy.hurtbox):
                    is_crit = random.random() < CRIT_CHANCE
                    final_damage = int(arrow.damage * CRIT_MULTIPLIER) if is_crit else arrow.damage
                    old_hp = enemy.hp
                    enemy.take_damage(final_damage, source_x=arrow.rect.centerx, is_crit=is_crit)
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        
                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)
                    if hasattr(hb.owner, 'attack_buff'):
                        if hb.owner.attack_buff == 'slow':
                            enemy.apply_debuff('slow', 3000) # Làm chậm 3 giây
                        elif hb.owner.attack_buff == 'burn':
                            enemy.apply_debuff('burn', 4000) # Thiêu đốt 4 giây
                    arrow.kill()
                    break

        # 2b. Ultimate Beam vs Enemy Hurtbox (piercing)
        for beam in list(self.ultimate_beams):
            if not beam.alive():
                continue
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                # Vertical depth filter
                if math.fabs(beam.floor_y - enemy.foot_y) > 60:
                    continue
                if beam.rect.colliderect(enemy.hurtbox) and beam.can_hit(enemy):
                    is_crit = random.random() < CRIT_CHANCE
                    final_damage = int(beam.damage * CRIT_MULTIPLIER) if is_crit else beam.damage
                    old_hp = enemy.hp
                    enemy.take_damage(final_damage, source_x=beam.rect.centerx, is_crit=is_crit)
                    beam.register_hit(enemy)
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        
                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)

        # 2c. Knight Ultimate Shockwave vs Enemy Hurtbox (immense knockback, piercing)
        for shockwave in list(self.knight_shockwaves):
            if not shockwave.alive():
                continue
            shockwave_hit = False
            for enemy in self.enemies:
                if enemy.hp <= 0:
                    continue
                if shockwave.collides_with(enemy) and shockwave.can_hit(enemy):
                    is_crit = random.random() < CRIT_CHANCE
                    old_hp = enemy.hp
                    
                    # Determine if enemy is in the front or rear of the knight's ultimate
                    if shockwave.facing == 1:
                        is_front = enemy.hurtbox.centerx > shockwave.rect.centerx
                    else:
                        is_front = enemy.hurtbox.centerx < shockwave.rect.centerx
                    
                    if is_front:
                        final_damage = int(shockwave.damage * CRIT_MULTIPLIER) if is_crit else shockwave.damage
                    else:
                        base_dmg = shockwave.damage * 0.5
                        final_damage = int(base_dmg * CRIT_MULTIPLIER) if is_crit else int(base_dmg)

                    enemy.take_damage(final_damage, source_x=shockwave.rect.centerx, is_crit=is_crit)
                    
                    # Apply knockback AFTER take_damage to prevent it from being overwritten
                    if is_front:
                        knockback_dir = shockwave.facing
                        enemy.vel.x = knockback_dir * shockwave.knockback
                        enemy.hurt_timer = max(getattr(enemy, 'hurt_timer', 0), 600)
                    else:
                        enemy.vel.x = 0  # No knockback for rear hits
                        enemy.hurt_timer = max(getattr(enemy, 'hurt_timer', 0), 300)

                    shockwave.register_hit(enemy)
                    if enemy.hp < old_hp:
                        dmg_num = DamageNumber(enemy.hurtbox.centerx, enemy.hurtbox.top, final_damage, is_crit=is_crit)
                        self.damage_numbers.add(dmg_num)
                        
                        vfx_type = "death" if enemy.hp <= 0 else "hit"
                        blood = BloodVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y, vfx_type=vfx_type)
                        self.effects.add(blood)
                        hit_effect = HitVFX(enemy.hurtbox.centerx, enemy.hurtbox.centery, getattr(enemy, 'facing', 1), enemy.foot_y)
                        self.effects.add(hit_effect)
                    shockwave_hit = True
            # Trigger camera shake on impact
            if shockwave_hit:
                self.trigger_camera_shake(intensity=12)

        # 3. Enemy Attack Hitbox vs Player Hurtboxes
        for player in self.players:
            if player.hp > 0 and player.hurt_timer <= 0:
                for hb in list(self.enemy_attacks):
                    if id(player) in hb.already_hit_targets:
                        continue
                    if math.fabs(hb.owner.foot_y - player.foot_y) > 50:
                        continue
                    if hb.rect.colliderect(player.hurtbox):
                        hb.already_hit_targets.add(id(player))
                        old_hp = player.hp
                        player.take_damage(hb.damage, source_x=hb.owner.rect.centerx)
                        if player.hp < old_hp:
                            dmg_num = DamageNumber(player.hurtbox.centerx, player.hurtbox.top, hb.damage, is_crit=False)
                            self.damage_numbers.add(dmg_num)
                            vfx_type = "death" if player.hp <= 0 else "hit"
                            blood = BloodVFX(player.hurtbox.centerx, player.hurtbox.centery, getattr(player, 'facing', 1), player.foot_y, vfx_type=vfx_type)
                            self.effects.add(blood)
                            hit_effect = HitVFX(player.hurtbox.centerx, player.hurtbox.centery, getattr(player, 'facing', 1), player.foot_y)
                            self.effects.add(hit_effect)
                        break

        # 4. Enemy Projectile vs Player Hurtboxes
        for player in self.players:
            if player.hp > 0 and player.hurt_timer <= 0:
                for proj in list(self.enemy_projectiles):
                    if math.fabs(proj.floor_y - player.foot_y) > 50:
                        continue
                    if proj.rect.colliderect(player.hurtbox):
                        old_hp = player.hp
                        player.take_damage(proj.damage, source_x=proj.rect.centerx)
                        if player.hp < old_hp:
                            dmg_num = DamageNumber(player.hurtbox.centerx, player.hurtbox.top, proj.damage, is_crit=False)
                            self.damage_numbers.add(dmg_num)
                            vfx_type = "death" if player.hp <= 0 else "hit"
                            blood = BloodVFX(player.hurtbox.centerx, player.hurtbox.centery, getattr(player, 'facing', 1), player.foot_y, vfx_type=vfx_type)
                            self.effects.add(blood)
                            hit_effect = HitVFX(player.hurtbox.centerx, player.hurtbox.centery, getattr(player, 'facing', 1), player.foot_y)
                            self.effects.add(hit_effect)
                        proj.kill()

        # 5. Spawn potion
        for enemy in self.enemies:
            if enemy.hp <= 0 and not getattr(enemy, 'dropped_potion', False):
                enemy.dropped_potion = True
                if random.random() < 1:  # 25% tỷ lệ rơi vật phẩm
                    potion_class = random.choice([HealthPotion, IcePotion, FirePotion, PoisonPotion])
                    potion = potion_class(enemy.hurtbox.centerx, enemy.foot_y)
                    self.potions.add(potion)
                    self.all_sprites.add(potion)

        # 6. Take potion
        for player in self.players:
            if player.hp > 0:
                for potion in list(self.potions):
                    if player.hurtbox.colliderect(potion.rect):
                        if potion.type == 'health':
                            player.hp = min(player.max_hp, player.hp + potion.heal_amount)
                        elif potion.type == 'slow_buff':
                            player.attack_buff = 'slow'
                            player.buff_timer = 10000  # Buff kéo dài 10 giây
                        elif potion.type == 'burn_buff':
                            player.attack_buff = 'burn'
                            player.buff_timer = 10000  # Buff kéo dài 10 giây
                        elif potion.type == 'poison':
                            # Thuốc độc gây debuff trực tiếp cho người nhặt
                            player.apply_debuff('poison', 6000) # Trúng độc 6 giây
                        potion.kill()

    def draw(self):
        ox, oy = self.camera_offset
        self.screen.blit(self.map, (ox, oy))
        # Create a combined list of all entities that need Y-sorting
        render_list = (list(self.all_sprites) + list(self.arrows) +
                       list(self.enemy_projectiles) + list(self.effects))

        def get_sort_y(s):
            if hasattr(s, 'foot_y'):
                return s.foot_y
            elif hasattr(s, 'floor_y'):
                return s.floor_y
            elif hasattr(s, 'hurtbox'):
                return s.hurtbox.bottom
            else:
                return s.rect.bottom - getattr(s, 'current_pdy', 0)

        sorted_sprites = sorted(render_list, key=get_sort_y)

        # ── Shadow pre-pass (drawn before sprites so shadows are always under) ──
        for sprite in sorted_sprites:
            # Only draw shadows for characters (skip arrows, spears, hitboxes)
            if not hasattr(sprite, 'hurtbox'):
                continue
            # Skip fully invisible sprites (alpha == 0 means corpse already gone)
            entity_alpha = getattr(sprite, 'alpha', 255)
            if entity_alpha <= 0:
                continue
            hurtbox = sprite.hurtbox
            # Scale shadow width to roughly match the entity's footprint
            target_w = max(20, int(hurtbox.width * 1.4))
            if target_w not in self._shadow_cache:
                src_w, src_h = self._shadow_src.get_size()
                scaled_h = max(6, int(src_h * target_w / src_w))
                self._shadow_cache[target_w] = pygame.transform.scale(
                    self._shadow_src, (target_w, scaled_h)
                )
            shadow_surf = self._shadow_cache[target_w]
            # Fade the shadow in sync with the entity's death fade-out
            if entity_alpha < 255:
                shadow_surf = shadow_surf.copy()
                shadow_surf.fill((255, 255, 255, entity_alpha), special_flags=pygame.BLEND_RGBA_MULT)
            sx = hurtbox.centerx - shadow_surf.get_width() // 2 + ox
            sy = hurtbox.bottom - shadow_surf.get_height() // 2 + oy
            self.screen.blit(shadow_surf, (sx, sy))

        for sprite in sorted_sprites:
            self.screen.blit(sprite.image, (sprite.rect.x + ox, sprite.rect.y + oy))


        # Draw enemy health bars — always visible for living enemies
        for enemy in self.enemies:
            if getattr(enemy, 'health_bar', None) is not None and enemy.hp > 0:
                enemy.health_bar.draw(self.screen, enemy, self.camera_offset)

        # --- DEBUG: Hitbox / Hurtbox visualization ---
        if self.DEBUG_DRAW:
            # Green: character hurtboxes
            for sprite in self.all_sprites:
                if hasattr(sprite, 'hurtbox') and getattr(sprite, 'hp', 0) > 0:
                    r = sprite.hurtbox
                    pygame.draw.rect(self.screen, (0, 255, 0), (r.x + ox, r.y + oy, r.width, r.height), 2)
            # Red: player attack hitboxes
            for hb in self.attacks:
                r = hb.rect
                pygame.draw.rect(self.screen, (255, 0, 0), (r.x + ox, r.y + oy, r.width, r.height), 2)
            # Magenta: enemy attack hitboxes
            for hb in self.enemy_attacks:
                r = hb.rect
                pygame.draw.rect(self.screen, (255, 0, 255), (r.x + ox, r.y + oy, r.width, r.height), 2)
        # -----------------------------------------------


        # Draw damage number popups on top of everything
        for dmg in self.damage_numbers:
            self.screen.blit(dmg.image, (dmg.rect.x + ox, dmg.rect.y + oy))

        # HUD: player HP (drawn without camera offset)
        for idx, player in enumerate(self.players):
            label = "P1" if idx == 0 else "P2"
            self.draw_health_bar(player.hp, player.max_hp, offset=(idx * 220), label=label)

        # HUD: Knight ultimate cooldown indicator
        if any(isinstance(player, Knight) and player.hp > 0 for player in self.players):
            self.draw_knight_ultimate_hud()

        # Boss HP bar
        if self.selected_phase == 1 and self.boss_spawned:
            for e in self.enemies:
                if isinstance(e, GoblinTank) and e.hp > 0:
                    self.draw_boss_health_bar(e.hp, e.max_hp, "GOBLIN TANK")
                    break
        elif self.selected_phase == 3:
            for e in self.enemies:
                if isinstance(e, DeathBringer) and e.hp > 0:
                    self.draw_boss_health_bar(e.hp, e.max_hp, "DEATH BRINGER")
                    break
                elif isinstance(e, FatCultist) and e.hp > 0:
                    self.draw_boss_health_bar(e.hp, e.max_hp, "FAT CULTIST")
                    break

        # GAME OVER UI
        if all(player.hp <= 0 for player in self.players):
            font = pygame.font.SysFont('Arial', 64, bold=True)
            text = font.render("GAME OVER", True, (255, 0, 0))
            text_rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 50))
            self.screen.blit(text, text_rect)
            
            font_sub = pygame.font.SysFont('Arial', 32)
            sub_text = font_sub.render("Press 'R' to Restart", True, (255, 255, 255))
            sub_rect = sub_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30))
            self.screen.blit(sub_text, sub_rect)

        pygame.display.flip()

    def draw_health_bar(self, hp, max_hp, offset=0, label="P1"):
        w = 200
        h = 24
        x = 10 + offset
        y = 10
        ratio = max(0, hp) / max_hp
        font = pygame.font.SysFont('Arial', 16, bold=True)
        label_surf = font.render(label, True, (255, 255, 255))
        self.screen.blit(label_surf, (x, y + 30))
        pygame.draw.rect(self.screen, (60, 60, 60), (x - 2, y - 2, w + 4, h + 4))
        pygame.draw.rect(self.screen, (180, 40, 40), (x, y, w, h))
        pygame.draw.rect(self.screen, (60, 220, 90), (x, y, int(w * ratio), h))
        if hp <= 0:
            dead_surf = font.render("DEAD", True, (255, 80, 80))
            self.screen.blit(dead_surf, (x + 10, y + 2))

    def draw_knight_ultimate_hud(self):
        """Draw a golden circular ultimate-cooldown indicator for the Knight.

        Positioned just to the right of the HP bar.  When the ultimate is
        ready the ring glows bright gold; while on cooldown a grey arc shows
        the remaining wait time and a gold fill arc shows what has recharged.
        """
        from config import KNIGHT_ULTIMATE_COOLDOWN
        cx, cy = 240, 21   # centre of the indicator circle
        radius  = 18
        thickness = 4

        knight = next((player for player in self.players if isinstance(player, Knight)), None)
        if knight is None:
            return
        cd = max(0.0, getattr(knight, 'ultimate_cooldown', 0))
        ready = cd <= 0

        if ready:
            # Bright golden full ring + glow
            pygame.draw.circle(self.screen, (255, 200, 40), (cx, cy), radius + 3, 1)
            pygame.draw.circle(self.screen, (255, 200, 40), (cx, cy), radius, thickness + 1)
            pygame.draw.circle(self.screen, (255, 240, 120), (cx, cy), radius - thickness, 0)
        else:
            # Dark background disc
            pygame.draw.circle(self.screen, (40, 40, 40), (cx, cy), radius, 0)
            # Grey "empty" arc
            pygame.draw.circle(self.screen, (100, 100, 100), (cx, cy), radius, thickness)
            # Gold "filled" arc representing progress (drawn as a series of lines)
            progress = 1.0 - cd / KNIGHT_ULTIMATE_COOLDOWN
            import math as _m
            start_angle = -_m.pi / 2          # 12 o'clock
            sweep       = 2 * _m.pi * progress
            steps       = max(1, int(60 * progress))
            for i in range(steps + 1):
                angle = start_angle + sweep * i / max(1, steps)
                px = int(cx + radius * _m.cos(angle))
                py = int(cy + radius * _m.sin(angle))
                pygame.draw.circle(self.screen, (220, 160, 20), (px, py), thickness // 2 + 1)

        # Label
        font_ult = pygame.font.SysFont('Arial', 11, bold=True)
        label_color = (255, 230, 80) if ready else (160, 140, 60)
        lbl = font_ult.render("ULTIMATE [L]", True, label_color)
        self.screen.blit(lbl, lbl.get_rect(center=(cx, cy + radius + 9)))

    def draw_boss_health_bar(self, hp, max_hp, boss_name="BOSS"):
        """Draw a large boss health bar at the bottom of the screen."""
        bar_w = 400
        bar_h = 14
        x = (WIDTH - bar_w) // 2
        y = HEIGHT - 40
        ratio = max(0, hp) / max_hp

        # Label
        font = pygame.font.SysFont('Arial', 18, bold=True)
        label = font.render(boss_name, True, (255, 200, 100))
        self.screen.blit(label, label.get_rect(center=(WIDTH // 2, y - 14)))

        # Bar background
        pygame.draw.rect(self.screen, (40, 40, 40), (x - 2, y - 2, bar_w + 4, bar_h + 4))
        # Red base
        pygame.draw.rect(self.screen, (180, 30, 30), (x, y, bar_w, bar_h))
        # Orange fill
        pygame.draw.rect(self.screen, (220, 120, 20), (x, y, int(bar_w * ratio), bar_h))

