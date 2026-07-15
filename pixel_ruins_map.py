"""1:1 renderer for the Pixel Ruins arena.

The overview and every texture atlas stay at their native pixel size.  Details
and their collision areas are read from ``pixel_ruins_layout.json``, which is
authored with ``pixel_ruins_tuner.py``.
"""

import json
from pathlib import Path

import pygame


MAP_DIR = Path(__file__).parent / "assets" / "maps" / "Pixel Art Top Down - Basic v1.2.3"
OVERVIEW_PATH = MAP_DIR / "Scene Overview.png"
LAYOUT_PATH = Path(__file__).parent / "assets" / "maps" / "pixel_ruins_layout.json"

TEXTURE_PATHS = {
    'wall': MAP_DIR / "Texture" / "TX Tileset Wall.png",
    'struct': MAP_DIR / "Texture" / "TX Struct.png",
    'props': MAP_DIR / "Texture" / "TX Props.png",
    'plant': MAP_DIR / "Texture" / "TX Plant.png",
    'player': MAP_DIR / "Texture" / "TX Player.png",
    'shadow_plant': MAP_DIR / "Texture" / "TX Shadow Plant.png",
    'grass': MAP_DIR / "Texture" / "TX Tileset Grass.png",
    'stone_ground': MAP_DIR / "Texture" / "TX Tileset Stone Ground.png",
    'shadow': MAP_DIR / "Texture" / "TX Shadow.png",
}


class PixelRuinsMap:
    """Render the overview at 1:1 and overlay JSON-authored texture details."""

    def __init__(self, width: int, height: int):
        # width/height are kept for API compatibility with Game, while the
        # playable surface itself uses the full native overview dimensions.
        self.width = width
        self.height = height
        self.wall_rects: list[pygame.Rect] = []
        self._textures = self._load_textures()
        self.world_surface = self._load_overview()
        self.surface = self.world_surface
        self.layout = self._load_layout()
        self.collision_zones = self._rectangles_from_layout('collision_zones')
        self.tunnels = self._rectangles_from_layout('tunnels')
        self.map_boundaries = self._lines_from_layout('map_boundaries')
        self.floors = self._regions_from_layout('floors')
        self.stairs = self._regions_from_layout('stairs')
        self.wall_rects.extend(self._cut_tunnels_from_colliders(self.collision_zones, self.tunnels))
        self.wall_rects.extend(self._line_collision_rects(self.map_boundaries))
        self._draw()

    def _load_textures(self):
        textures = {}
        for name, path in TEXTURE_PATHS.items():
            try:
                textures[name] = pygame.image.load(str(path)).convert_alpha()
            except Exception:
                textures[name] = pygame.Surface((1, 1), pygame.SRCALPHA)
        return textures

    def _load_overview(self):
        try:
            overview = pygame.image.load(str(OVERVIEW_PATH)).convert()
        except Exception:
            overview = pygame.Surface((self.width, self.height))
            overview.fill((45, 55, 45))
        # Keep every overview/detail pixel at native 1:1 size.  Game draws a
        # moving 960x640 viewport over this full surface.
        return overview

    def _load_layout(self):
        try:
            with LAYOUT_PATH.open('r', encoding='utf-8') as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {'details': []}
        except (OSError, json.JSONDecodeError):
            return {'details': []}

    def _draw(self):
        for detail in self.layout.get('details', []):
            texture = self._textures.get(detail.get('texture'))
            source_data = detail.get('source', [])
            position = detail.get('position', [])
            if texture is None or len(source_data) != 4 or len(position) != 2:
                continue
            source = pygame.Rect(source_data)
            if source.width <= 0 or source.height <= 0:
                continue
            if source.left < 0 or source.top < 0 or source.right > texture.get_width() or source.bottom > texture.get_height():
                continue
            world_pos = (int(position[0]), int(position[1]))
            self.surface.blit(texture, world_pos, source)

    def _rectangles_from_layout(self, key):
        """Read only explicit tuner-authored rectangles as collision zones."""
        rectangles = []
        for zone in self.layout.get(key, []):
            rect_data = zone.get('rect', []) if isinstance(zone, dict) else zone
            if not isinstance(rect_data, list) or len(rect_data) != 4:
                continue
            rect = pygame.Rect(*(int(value) for value in rect_data))
            if rect.width > 0 and rect.height > 0:
                rectangles.append(rect)
        return rectangles

    def _regions_from_layout(self, key):
        regions = []
        for index, region in enumerate(self.layout.get(key, [])):
            if not isinstance(region, dict):
                continue
            rect_data = region.get('rect', [])
            if not isinstance(rect_data, list) or len(rect_data) != 4:
                continue
            rect = pygame.Rect(*(int(value) for value in rect_data))
            if rect.width <= 0 or rect.height <= 0:
                continue
            copy = dict(region)
            copy['rect'] = rect
            copy.setdefault('id', index + 1)
            regions.append(copy)
        return regions

    def _lines_from_layout(self, key):
        lines = []
        for line in self.layout.get(key, []):
            if not isinstance(line, dict):
                continue
            start, end = line.get('start', []), line.get('end', [])
            if not (isinstance(start, list) and isinstance(end, list) and len(start) == len(end) == 2):
                continue
            start = (int(start[0]), int(start[1]))
            end = (int(end[0]), int(end[1]))
            if start != end:
                lines.append((start, end))
        return lines

    @staticmethod
    def _line_collision_rects(lines, thickness=8):
        """Approximate arbitrary boundary lines with overlapping small blocks."""
        rectangles = []
        half = thickness // 2
        for start, end in lines:
            dx, dy = end[0] - start[0], end[1] - start[1]
            steps = max(1, int(max(abs(dx), abs(dy)) / 3))
            for step in range(steps + 1):
                ratio = step / steps
                x = round(start[0] + dx * ratio)
                y = round(start[1] + dy * ratio)
                rectangles.append(pygame.Rect(x - half, y - half, thickness, thickness))
        return rectangles

    @staticmethod
    def _cut_tunnels_from_colliders(colliders, tunnels):
        """Subtract every tunnel area from authored collision rectangles."""
        remaining = list(colliders)
        for tunnel in tunnels:
            next_remaining = []
            for collider in remaining:
                overlap = collider.clip(tunnel)
                if not overlap:
                    next_remaining.append(collider)
                    continue
                # Four rectangles cover everything around the removed centre.
                candidates = (
                    pygame.Rect(collider.left, collider.top, collider.width, overlap.top - collider.top),
                    pygame.Rect(collider.left, overlap.bottom, collider.width, collider.bottom - overlap.bottom),
                    pygame.Rect(collider.left, overlap.top, overlap.left - collider.left, overlap.height),
                    pygame.Rect(overlap.right, overlap.top, collider.right - overlap.right, overlap.height),
                )
                next_remaining.extend(rect for rect in candidates if rect.width > 0 and rect.height > 0)
            remaining = next_remaining
        return remaining

    def floor_at(self, world_position):
        """Return the last matching floor so smaller overlay zones win."""
        floor = None
        for candidate in self.floors:
            if candidate['rect'].collidepoint(world_position):
                floor = candidate
        return floor
