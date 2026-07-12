# A Twisted Fate - Beat-em-up Game (pygame)

A side-scrolling beat-em-up action game built with pygame using object-oriented design patterns. Features multiple heroes, enemy waves, boss battles, and a combo attack system.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Game

```bash
python main.py
```

## Game Features

- **Hero Selection**: Choose between Knight and Archer
- **4 Phases**: Goblin Invasion, The Menagerie, The Cult, Pixel Ruins Arena
- **Combat System**: 
  - 3-hit combo attacks
  - Defense mechanics
  - Ultimate abilities
  - Special projectile attacks (Archer)
- **Enemy Variety**: Multiple enemy types with unique attack patterns
- **Boss Battles**: Boss encounter in each phase
- **Visual Effects**: Blood effects, hit feedback, damage numbers, camera shake

## Controls

### Menu Navigation
- **1**: Select Knight / Select Phase 1 (Goblin Invasion)
- **2**: Select Archer / Select Phase 2 (The Menagerie)
- **3**: Select Phase 3 (The Cult)
- **4**: Select Phase 4 (Pixel Ruins Arena)
- **ESC**: Go back
- **R**: Restart after defeat

### Gameplay
- **← / A**: Move left
- **→ / D**: Move right
- **↑ / W**: Move up
- **↓ / S**: Move down
- **J**: Attack (3-hit combo)
- **K**: Defend
- **L**: Ultimate ability

## Project Structure

```
├── main.py              # Game entry point
├── game.py              # Main game loop & state management
├── entities.py          # Player and enemy classes
├── sprites.py           # Sprite animation system
├── config.py            # Configuration and constants
├── box_tool.py          # Sprite hitbox editor tool
├── pivot_tool.py        # Sprite pivot point editor tool
├── requirements.txt     # Dependencies
└── assets/              # Game assets
    ├── maps/            # Background images
    ├── hero/            # Player spritesheets
    │   ├── knight/
    │   └── archer/
    ├── monsters/        # Enemy spritesheets
    │   ├── goblin_tank/
    │   ├── goblin_warrior/
    │   ├── goblin_spearman/
    │   ├── lizardman/
    │   ├── kobold/
    │   ├── fire_worm/
    │   ├── cyclop/
    │   ├── skeleton/
    │   ├── troll/
    │   ├── fat_cultist/
    │   └── bringer_of_death/
    ├── vfx/             # Visual effects
    ├── animation_metadata.json  # Animation frame data
    └── font/            # Font files
```

## Configuration

Game settings are in `config.py`:
- Screen dimensions (WIDTH, HEIGHT)
- FPS and physics constants
- Asset paths
- Collision boundaries
- Attack ranges and damage values

## Tools

### Sprite Box Editor (`box_tool.py`)
Edit sprite hitboxes and hurtboxes.
- Arrow keys: Move
- H: Toggle hurtbox
- B: Toggle hitbox
- SPACE: Next frame
- R: Reset
- S: Save
- ESC: Exit

### Sprite Pivot Editor (`pivot_tool.py`)
Adjust sprite pivot points.
- Arrow keys: Move pivot
- ESC: Exit

## Notes

- Animation frames are defined in `animation_metadata.json`
- Collision detection uses rectangular hitboxes with depth filtering
- Damage numbers and effects provide visual feedback for combat actions
- Each enemy type has unique AI and attack patterns
