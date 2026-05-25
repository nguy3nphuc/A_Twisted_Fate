# Beat-em-up Test (pygame)

This is a small draft/testing beat-em-up built with pygame using OOP patterns.

Quick start:

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Put your assets under the `assets/` folder. Default config paths are in `config.py`:

- `assets/maps/level1.png` — background or tilemap image (optional)
- `assets/hero/knight/spritesheet.png` — player spritesheet
- `assets/monsters/Skeleton/Sprite Sheets/skeleton.png` — enemy spritesheet

3. Run:

```bash
python main.py
```

Controls:
- Left/Right or A/D: move
- Z or Space: attack

Notes:
- Code is intentionally simple and designed as a starting point. Replace spritesheet loading sizes in `entities.py` to match your sheets.
- The attack uses a short-lived rectangular hitbox. Tweak `AttackHitbox` and damage values as needed.
