"""Render the native-size Pixel Ruins overview plus JSON layout to a PNG."""

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).parent
MAP_DIR = ROOT / 'assets' / 'maps' / 'Pixel Art Top Down - Basic v1.2.3'
LAYOUT_PATH = ROOT / 'assets' / 'maps' / 'pixel_ruins_layout.json'
OUTPUT_PATH = ROOT / 'assets' / 'maps' / 'pixel_ruins_preview.png'
GAME_VIEWPORT_PATH = ROOT / 'assets' / 'maps' / 'pixel_ruins_preview_game.png'

TEXTURES = {
    'wall': MAP_DIR / 'Texture' / 'TX Tileset Wall.png',
    'struct': MAP_DIR / 'Texture' / 'TX Struct.png',
    'props': MAP_DIR / 'Texture' / 'TX Props.png',
    'plant': MAP_DIR / 'Texture' / 'TX Plant.png',
    'grass': MAP_DIR / 'Texture' / 'TX Tileset Grass.png',
    'stone_ground': MAP_DIR / 'Texture' / 'TX Tileset Stone Ground.png',
    'shadow': MAP_DIR / 'Texture' / 'TX Shadow.png',
}


def main():
    with LAYOUT_PATH.open(encoding='utf-8') as file:
        layout = json.load(file)

    canvas = Image.open(MAP_DIR / 'Scene Overview.png').convert('RGBA')
    atlases = {name: Image.open(path).convert('RGBA') for name, path in TEXTURES.items()}

    drawn = 0
    for detail in layout.get('details', []):
        atlas = atlases.get(detail.get('texture'))
        source = detail.get('source', [])
        position = detail.get('position', [])
        if atlas is None or len(source) != 4 or len(position) != 2:
            continue
        x, y, w, h = map(int, source)
        px, py = map(int, position)
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > atlas.width or y + h > atlas.height:
            continue
        canvas.alpha_composite(atlas.crop((x, y, x + w, y + h)), (px, py))
        drawn += 1

    canvas.save(OUTPUT_PATH)
    left = max(0, (canvas.width - 960) // 2)
    top = max(0, (canvas.height - 640) // 2)
    canvas.crop((left, top, left + 960, top + 640)).save(GAME_VIEWPORT_PATH)
    print(f'Rendered {drawn} details to {OUTPUT_PATH} and {GAME_VIEWPORT_PATH}')


if __name__ == '__main__':
    main()
