# Infiniz Fantasy - Co-op Beat'em-up (pygame)

Infiniz Fantasy is a 2-player local co-op beat-em-up built with Python and pygame. The game mixes action combat, enemy waves, boss encounters, skill drops, and passive effects in a stylized arcade presentation.

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the game

```bash
python main.py
```

## What’s in the game

- 2-player local co-op gameplay
- Two playable heroes:
  - Knight: melee combat, defense, ultimate shockwave
  - Archer: ranged attacks, dashes, ultimate beam, magic arrows
- 4 phases:
  - Phase 1: Goblin Invasion
  - Phase 2: The Menagerie
  - Phase 3: The Cult
  - Phase 4: Pixel Ruins Arena
- Combat systems including:
  - combo attacks
  - blocking/defense
  - ultimate abilities
  - projectile and spell effects
  - damage numbers and visual VFX
- Enemy variety with unique movement and attack patterns
- Boss and miniboss encounters
- Skill drops and upgradeable player abilities
- Auto-respawn after 20 seconds if the teammate is still alive

## Controls

### Menu / navigation
- 1 / 2 / 3 / 4: choose hero / phase
- ESC: pause or go back
- R: restart after defeat

### Player 1 (Knight)
- A / D / W / S: move
- J: attack
- K: defend
- L: ultimate

### Player 2 (Archer)
- Arrow keys: move
- NumPad 1 / 4: attack
- NumPad 2 / 5: dash
- NumPad 3 / 6: ultimate
- NumPad 0: cycle magic arrow type

### Skills
- N: cycle P1 target skill
- M: use P1 target skill
- 7 / 8: cycle and use P2 target skill

## Project structure

```text
├── main.py                      # Game entry point
├── config.py                    # Game balance, constants, and config
├── requirements.txt             # Python dependencies
├── assets/                      # Sprites, maps, VFX, animations, fonts
├── entities/                    # Heroes, enemies, items, VFX classes
├── game/                        # Game loop and gameplay systems
│   ├── game_engine.py           # Main engine and update/render loop
│   ├── skills_projectiles.py    # Skill/projectile logic
│   └── respawn.py               # Auto-respawn timing helper
├── tools/                       # Utilities for map, pivot, hitbox editing
└── tests/                       # Unit tests for gameplay helpers
```

## Configuration and tuning

The gameplay balance and constants are defined in:
- config.py
- assets/animation_metadata.json
- assets/skills/ui_tune.json

These files control:
- screen size and FPS
- combat values and cooldowns
- enemy stats and behavior
- skill UI layout and animation timing

## Development notes

- Animation frames and metadata are loaded from assets/animation_metadata.json
- Collision logic uses hurtboxes/hitboxes with depth filtering
- The engine is organized around sprite groups and per-frame update/render flow
- The project also includes debugging and asset-authoring tools in the tools/ folder
