# Basic configuration for the test beat-em-up
WIDTH = 960
HEIGHT = 640
FPS = 60

# Asset paths (adjust names to match your files)
MAP_IMAGE = "assets/maps/map1.jpeg"
PLAYER_SPRITESHEET = "assets/hero/knight/spritesheet.png"
EFFECT_SPRITESHEET = "assets/effects/effects.png"
ARCHER_DIR = "assets/hero/archer"
ARROW_IMAGE = "assets/hero/archer/arrow.png"

# Goblin Asset Paths
GOBLIN_TANK_DIR = "assets/monsters/goblin_tank"
GOBLIN_WARRIOR_DIR = "assets/monsters/goblin_warrior"
GOBLIN_SPEARMAN_DIR = "assets/monsters/goblin_spearman"
SPEAR_IMAGE = "assets/monsters/goblin_spearman/spear.png"

# Moveable area boundaries (these are rect.bottom values, i.e. where feet land)
# Adjust these to match the dirt road area on your map
MIN_Y = 190   # top of the dirt road (below the back grass/bushes)
MAX_Y = 530   # bottom of the dirt road (above the foreground grass)
MIN_X = 0
MAX_X = WIDTH

# Player Settings

# Enemy Attack Settings (shared offset)
ENEMY_ATTACK_OFFSET_Y = 0      # vertical offset for enemy melee attack boxes

# Goblin Tank Attack Settings (boss)
GOBLIN_TANK_ATTACK_RANGE_X = 80
GOBLIN_TANK_ATTACK_RANGE_Y = 40
GOBLIN_TANK_ATTACK_2_RANGE_X = 120
GOBLIN_TANK_ATTACK_2_RANGE_Y = 60

# Goblin Warrior Attack Settings
GOBLIN_WARRIOR_ATTACK_RANGE_X = 55
GOBLIN_WARRIOR_ATTACK_RANGE_Y = 30

# Goblin Spearman Attack Settings
GOBLIN_SPEARMAN_ATTACK_RANGE_X = 65
GOBLIN_SPEARMAN_ATTACK_RANGE_Y = 30

# ── Phase 1 New Monsters ─────────────────────────────────────────────────────

# Lizardman (standard 2-hit melee)
LIZARDMAN_ATTACK_RANGE_X = 75
LIZARDMAN_ATTACK_RANGE_Y = 40

# Cyclop (heavy hitter with special attack2 on cooldown)
CYCLOP_ATTACK_RANGE_X = 90
CYCLOP_ATTACK_RANGE_Y = 45
CYCLOP_SPECIAL_COOLDOWN = 5000   # ms between attack2 uses

# Kobold (assassin — dash special + normal combo)
KOBOLD_ATTACK_RANGE_X = 60
KOBOLD_ATTACK_RANGE_Y = 35
KOBOLD_DASH_RANGE_X = 150        # horizontal range that triggers the dash
KOBOLD_DASH_RANGE_Y = 40
KOBOLD_DASH_COOLDOWN = 6000      # ms cooldown between dash special attacks

# ── Phase 3 New Monsters (Map 3) ─────────────────────────────────────────────

# Fat Cultist (miniboss, similar to tank)
FAT_CULTIST_ATTACK_RANGE_X = 80
FAT_CULTIST_ATTACK_RANGE_Y = 40
FAT_CULTIST_ATTACK_2_RANGE_X = 120
FAT_CULTIST_ATTACK_2_RANGE_Y = 60

# Death Bringer (boss)
DEATH_BRINGER_ATTACK_RANGE_X = 70
DEATH_BRINGER_ATTACK_RANGE_Y = 40
DEATH_BRINGER_CAST_RANGE_X = 350
DEATH_BRINGER_CAST_RANGE_Y = 150
DEATH_BRINGER_SPELL_COOLDOWN = 7000

# Fireworm (ranged, shorter range than spearman)
FIREWORM_ATTACK_RANGE = 320      # ~WIDTH/3, must close more than spearman (WIDTH/2)
FIREBALL_SPEED = 8               # pixels per frame

# Camera Shake Settings
CAMERA_SHAKE_INTENSITY = 6     # max pixel offset per shake event
CAMERA_SHAKE_DURATION = 200    # ms per shake event

# Death fade-out settings
DEATH_FADE_DELAY = 500         # ms to wait after death anim finishes before fading
DEATH_FADE_DURATION = 1000     # ms for the fade-out effect

# Archer Ultimate Skill Settings
ARCHER_ULTIMATE_DAMAGE = 40        # damage per hit of the ultimate beam
ARCHER_ULTIMATE_SPEED = 18         # pixels per frame the beam travels
ARCHER_ULTIMATE_COOLDOWN = 8000    # ms cooldown between ultimates
ARCHER_ULTIMATE_CAST_FRAME = 12    # animation frame at which the beam is spawned (0-indexed)
DASH_SMOKE_IMAGE = "assets/hero/archer/dash_smoke.png"
ULTIMATE_EFFECT_IMAGE = "assets/hero/archer/archer_ultimate_effect.png"

# Knight Ultimate Skill Settings
KNIGHT_ULTIMATE_DAMAGE = 80            # base damage of the shockwave slam
KNIGHT_ULTIMATE_KNOCKBACK = 28         # pixel velocity knocked back per hit (immense)
KNIGHT_ULTIMATE_COOLDOWN = 10000       # ms cooldown between knight ultimates
KNIGHT_ULTIMATE_CAST_FRAME = 34        # animation frame at which the shockwave is spawned (0-indexed)

# Font
DAMAGE_FONT_PATH = "assets/font/BoldPixels.ttf"

# Critical Hit Settings
CRIT_CHANCE = 0.20             # 20% chance to land a critical hit
CRIT_MULTIPLIER = 2.0          # critical hits deal 2x damage

# Damage Number Settings
DAMAGE_NUMBER_FONT_SIZE = 32           # base font size for normal hits
DAMAGE_NUMBER_CRIT_FONT_SIZE = 40      # font size for critical hits
DAMAGE_NUMBER_RISE_SPEED = 1.5         # pixels per frame the number floats up
DAMAGE_NUMBER_DURATION = 800           # ms before the number disappears
DAMAGE_NUMBER_COLOR = (255, 50, 50)            # red for normal damage
DAMAGE_NUMBER_CRIT_COLOR = (255, 20, 20)       # deeper red for critical hits
