# Basic configuration for the test beat-em-up
WIDTH = 960
HEIGHT = 640
FPS = 60

# Asset paths (adjust names to match your files)
MAP_IMAGE = "assets/maps/map1.jpeg"
PLAYER_SPRITESHEET = "assets/hero/knight/spritesheet.png"
ENEMY_SPRITESHEET = "assets/monsters/Skeleton/Sprite Sheets/skeleton.png"
EFFECT_SPRITESHEET = "assets/effects/effects.png"
ARCHER_DIR = "assets/hero/archer"
ARROW_IMAGE = "assets/hero/archer/Arrow.png"

# Moveable area boundaries (these are rect.bottom values, i.e. where feet land)
# Adjust these to match the dirt road area on your map
MIN_Y = 190   # top of the dirt road (below the back grass/bushes)
MAX_Y = 530   # bottom of the dirt road (above the foreground grass)
MIN_X = 0
MAX_X = WIDTH

# Player Attack Settings
# You can manually change these values to adjust the size of the attack rectangle
PLAYER_ATTACK_WIDTH = 50       # width of the attack hitbox rectangle
PLAYER_ATTACK_HEIGHT = 60      # height of the attack hitbox rectangle
PLAYER_ATTACK_OFFSET_X = 10    # horizontal gap from sprite edge to hitbox start

# Enemy Attack Settings
ENEMY_ATTACK_RANGE_X = 60      # horizontal range for skeleton melee attack
ENEMY_ATTACK_RANGE_Y = 30      # vertical range for skeleton melee attack

# Death fade-out settings
DEATH_FADE_DELAY = 500         # ms to wait after death anim finishes before fading
DEATH_FADE_DURATION = 1000     # ms for the fade-out effect
