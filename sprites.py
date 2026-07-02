import pygame
import os
import json


# ---------------------------------------------------------------------------
# Animation Metadata
# ---------------------------------------------------------------------------
# Load frame-count metadata from a JSON file.  This file stores the number of
# frames, duration, loop flag, source filename, scale, and folder path for
# every animation of every character.  Actual pixel dimensions are computed at
# load time from the spritesheet image width — no hardcoded sizes anywhere.
# ---------------------------------------------------------------------------
_METADATA_PATH = os.path.join(os.path.dirname(__file__), "assets", "animation_metadata.json")
_ANIMATION_METADATA = {}

try:
    with open(_METADATA_PATH, "r") as _f:
        _ANIMATION_METADATA = json.load(_f)
except FileNotFoundError:
    print(f"[WARNING] Animation metadata file not found: {_METADATA_PATH}")
except json.JSONDecodeError as e:
    print(f"[WARNING] Invalid JSON in animation metadata: {_METADATA_PATH}: {e}")


class SpriteSheet:
    """Loads a single image and provides methods to extract sub-surfaces."""

    def __init__(self, filename):
        try:
            self.sheet = pygame.image.load(filename).convert_alpha()
        except Exception as e:
            print(f"[WARNING] Failed to load spritesheet image: {filename} ({e})")
            self.sheet = None

    def image_at(self, rectangle, colorkey=None):
        """Extract a single sub-image at the given (x, y, w, h) rectangle."""
        if self.sheet is None:
            surf = pygame.Surface((rectangle[2], rectangle[3]), pygame.SRCALPHA)
            surf.fill((255, 0, 255, 255))
            return surf
        rect = pygame.Rect(rectangle)
        image = pygame.Surface(rect.size, pygame.SRCALPHA)
        image.blit(self.sheet, (0, 0), rect)
        return image

    def load_strip(self, rect, image_count, colorkey=None):
        """Load a horizontal strip of *image_count* frames from a grid-based
        spritesheet, starting at *rect* = (x, y, w, h)."""
        frames = []
        x, y, w, h = rect
        for i in range(image_count):
            frames.append(self.image_at((x + i * w, y, w, h), colorkey))
        return frames

    def load_horizontal_strip(self, frame_count, scale=1.0):
        """Slice a horizontal spritesheet into *frame_count* equal-width frames.

        * ``frame_width`` is calculated as ``image_width // frame_count``.
        * ``frame_height`` is the full image height.
        * Each frame is optionally scaled by *scale*.

        Returns a list of Surfaces, or an empty list if the sheet failed to load.
        """
        if self.sheet is None:
            return []

        img_w = self.sheet.get_width()
        img_h = self.sheet.get_height()
        frame_w = img_w // frame_count

        frames = []
        for i in range(frame_count):
            sub = pygame.Surface((frame_w, img_h), pygame.SRCALPHA)
            sub.blit(self.sheet, (0, 0), (i * frame_w, 0, frame_w, img_h))
            if scale != 1.0:
                sub = pygame.transform.scale(
                    sub, (int(frame_w * scale), int(img_h * scale))
                )
            frames.append(sub)
        return frames

    def load_horizontal_strip_with_anchors(self, frame_count, scale=1.0):
        """Like load_horizontal_strip, but also returns per-frame anchor offsets.

        For each frame, computes the bounding box of the visible pixels and
        returns an anchor offset ``(ox, oy)`` representing the distance from
        the frame's center-bottom to the visible content's center-bottom.

        Returns ``(frames_list, anchors_list)`` where each anchor is ``(ox, oy)``.
        """
        if self.sheet is None:
            return [], []

        img_w = self.sheet.get_width()
        img_h = self.sheet.get_height()
        frame_w = img_w // frame_count

        frames = []
        anchors = []
        for i in range(frame_count):
            sub = pygame.Surface((frame_w, img_h), pygame.SRCALPHA)
            sub.blit(self.sheet, (0, 0), (i * frame_w, 0, frame_w, img_h))

            # Compute bounding rect on unscaled frame for accuracy
            bbox = sub.get_bounding_rect()
            if bbox.width == 0 or bbox.height == 0:
                # Empty frame — no offset
                anchors.append((0, 0))
            else:
                # The frame's midbottom is at (frame_w // 2, img_h).
                # The visible body's center-bottom is at (bbox.centerx, bbox.bottom).
                # The offset to shift the draw position so the body center
                # aligns with where midbottom says the character is:
                ox = bbox.centerx - frame_w // 2
                oy = bbox.bottom - img_h  # negative or zero: how far up from canvas bottom
                anchors.append((int(ox * scale), int(oy * scale)))

            if scale != 1.0:
                sub = pygame.transform.scale(
                    sub, (int(frame_w * scale), int(img_h * scale))
                )
            frames.append(sub)
        return frames, anchors


class Animator:
    """Simple state-based animator.
    states_frames: dict of state -> list of Surface frames
    durations: dict of state -> frame duration in ms
    anchors: dict of state -> list of (ox, oy) per-frame anchor offsets
    """
    def __init__(self, states_frames, durations=None, default_state=None, loop_states=None, anchors=None, pivot_deltas=None, hit_frames=None, states_config=None):
        self.states = states_frames
        self.durations = durations or {}
        self.loop_states = loop_states or set()
        self.anchors = anchors or {}
        self.pivot_deltas = pivot_deltas or {}
        # hit_frames: dict of state -> int frame index at which damage should be dealt.
        # If a state has no entry, is_at_hit_frame() falls back to the midpoint.
        self.hit_frames = hit_frames or {}
        # states_config: the raw per-animation config dict forwarded from metadata.
        # Contains hitbox_w/h/offset_x/y and hurtbox_w/h/offset_x for box_tool use.
        self.states_config = states_config or {}
        self.state = default_state or next(iter(states_frames))
        self.frame_index = 0
        self.time = 0
        self.finished = False

    @classmethod
    def from_config(cls, animation_config):
        """Create an Animator from a unified animation config dict.

        *animation_config* maps state names to dicts with keys:
            ``frames``   – list of Surface objects
            ``duration`` – int, ms per frame
            ``loop``     – bool, whether this animation loops
            ``anchors``  – (optional) list of (ox, oy) per-frame anchor offsets

        Example::

            {
                'idle': {'frames': [...], 'duration': 150, 'loop': True},
                'run':  {'frames': [...], 'duration': 100, 'loop': True},
                'hit':  {'frames': [...], 'duration': 100, 'loop': False},
            }
        """
        states_frames = {}
        durations = {}
        loop_states = set()
        anchors = {}
        pivot_deltas = {}
        hit_frames = {}

        for state_name, config in animation_config.items():
            states_frames[state_name] = config['frames']
            durations[state_name] = config.get('duration', 100)
            if config.get('loop', False):
                loop_states.add(state_name)
            if 'anchors' in config:
                anchors[state_name] = config['anchors']
            if 'pivot_delta' in config:
                pivot_deltas[state_name] = config['pivot_delta']
            if 'hit_frame' in config:
                hit_frames[state_name] = config['hit_frame']

        return cls(states_frames, durations, default_state='idle',
                   loop_states=loop_states, anchors=anchors,
                   pivot_deltas=pivot_deltas, hit_frames=hit_frames,
                   states_config=animation_config)

    def set_state(self, state, reset=True):
        if state not in self.states:
            return
        if self.state == state and not reset:
            return
        self.state = state
        self.frame_index = 0
        self.time = 0
        self.finished = False

    def update(self, dt):
        if self.finished:
            return
        frames = self.states[self.state]
        if len(frames) <= 1:
            return
        duration = self.durations.get(self.state, 100)
        self.time += dt
        while self.time >= duration:
            self.time -= duration
            self.frame_index += 1
            if self.frame_index >= len(frames):
                if self.state in self.loop_states:
                    self.frame_index = 0
                else:
                    self.frame_index = len(frames) - 1
                    self.finished = True

    def get_frame(self):
        return self.states[self.state][self.frame_index]

    def get_anchor_offset(self):
        """Return (ox, oy) anchor offset for the current frame.
        ox: how far the visual body center is from the frame's horizontal center
        oy: how far the visual body bottom is from the frame's bottom edge
        Returns (0, 0) if no anchor data is available.
        """
        state_anchors = self.anchors.get(self.state)
        if state_anchors and self.frame_index < len(state_anchors):
            return state_anchors[self.frame_index]
        return (0, 0)

    def get_pivot_delta(self):
        """Return (dx, dy) static pivot correction for the current state.

        This is a constant offset per animation state (NOT per frame) that
        compensates for canvas-size differences between animations.  Apply
        it to ``self.rect`` after anchoring at ``midbottom`` so the
        character's feet stay locked to the same screen position.

        When the sprite is flipped (facing == -1), the caller must negate
        the horizontal component:  ``dx = -dx``.
        """
        return self.pivot_deltas.get(self.state, (0, 0))

    def is_at_hit_frame(self):
        """Return True when the current frame is the designated damage frame.

        If a ``hit_frame`` was specified for this animation state in
        ``animation_metadata.json``, that index is used.  Otherwise falls back
        to the midpoint of the strip (legacy behaviour).
        """
        frames = self.states[self.state]
        target = self.hit_frames.get(self.state, len(frames) // 2)
        if isinstance(target, list):
            return self.frame_index in target
        return self.frame_index == target

    def is_midpoint(self):
        """Legacy helper — prefer is_at_hit_frame() for new code."""
        frames = self.states[self.state]
        return self.frame_index == len(frames) // 2

    def is_finished(self):
        return self.finished


# ---------------------------------------------------------------------------
# Public API — metadata-driven animation loader
# ---------------------------------------------------------------------------

def load_character_animations(character_name, scale=None):
    """Load all animations for *character_name* using the JSON metadata.

    Returns a dict of ``state_name -> {'frames': [...], 'duration': int,
    'loop': bool}`` ready to be passed to ``Animator.from_config()``.

    * If the character has no metadata entry, prints a warning and returns ``{}``.
    * If an individual animation file is missing or fails to load, prints a
      warning with the character name, animation name, and file path, then
      skips that animation (no crash).
    """
    char_meta = _ANIMATION_METADATA.get(character_name)
    if char_meta is None:
        print(f"[WARNING] No animation metadata found for character "
              f"'{character_name}'. Skipping all animations.")
        return {}

    folder = char_meta.get("folder", "")
    if scale is None:
        scale = char_meta.get("scale", 1.0)

    animations = {}
    raw_pivots = {}       # state -> (pivot_x, pivot_y) in unscaled pixels
    raw_frame_dims = {}   # state -> (frame_w, frame_h)  in unscaled pixels

    for state_name, anim_info in char_meta.get("animations", {}).items():
        filename = anim_info.get("file", "")
        filepath = os.path.join(folder, filename)

        # --- File existence check with clear error message ---
        if not os.path.isfile(filepath):
            print(f"[WARNING] [{character_name}/{state_name}] "
                  f"Spritesheet file not found: {filepath}")
            continue

        # --- Load and slice the spritesheet ---
        ss = SpriteSheet(filepath)
        if ss.sheet is None:
            print(f"[WARNING] [{character_name}/{state_name}] "
                  f"Could not load image — skipping.")
            continue

        frame_count = anim_info.get("frames", 1)
        frames = ss.load_horizontal_strip(frame_count, scale=scale)

        if not frames:
            print(f"[WARNING] [{character_name}/{state_name}] "
                  f"No frames extracted from: {filepath}")
            continue

        # Record unscaled frame dimensions and pivot for delta computation
        unscaled_fw = ss.sheet.get_width() // frame_count
        unscaled_fh = ss.sheet.get_height()
        raw_frame_dims[state_name] = (unscaled_fw, unscaled_fh)
        raw_pivots[state_name] = (
            anim_info.get("pivot_x", unscaled_fw // 2),
            anim_info.get("pivot_y", unscaled_fh),
        )

        entry = {
            'frames': frames,
            'duration': anim_info.get("duration", 100),
            'loop': anim_info.get("loop", False),
        }
        # Forward the optional hit_frame so Animator can use it directly
        if 'hit_frame' in anim_info:
            entry['hit_frame'] = anim_info['hit_frame']

        # Forward attack hitbox dimensions (per-animation, only on attack states)
        # Apply scaling to transform unscaled JSON data to scaled game screen pixels
        if 'hitbox_w' in anim_info:
            entry['hitbox_w'] = int(anim_info['hitbox_w'] * scale)
        if 'hitbox_h' in anim_info:
            entry['hitbox_h'] = int(anim_info['hitbox_h'] * scale)
        if 'hitbox_offset_x' in anim_info:
            entry['hitbox_offset_x'] = int(anim_info['hitbox_offset_x'] * scale)
        if 'hitbox_offset_y' in anim_info:
            entry['hitbox_offset_y'] = int(anim_info['hitbox_offset_y'] * scale)

        animations[state_name] = entry

    # Forward character-level hurtbox data into every animation entry so
    # entities can retrieve it from any state's config dict.
    hb_w  = char_meta.get('hurtbox_w')
    hb_h  = char_meta.get('hurtbox_h')
    hb_ox = char_meta.get('hurtbox_offset_x')
    if hb_w is not None:
        scaled_hb_w = int(hb_w * scale)
        scaled_hb_h = int(hb_h * scale) if hb_h is not None else int(1 * scale)
        scaled_hb_ox = int(hb_ox * scale) if hb_ox is not None else 0
        for entry in animations.values():
            entry.setdefault('hurtbox_w',        scaled_hb_w)
            entry.setdefault('hurtbox_h',        scaled_hb_h)
            entry.setdefault('hurtbox_offset_x', scaled_hb_ox)

    # --- Compute static pivot deltas relative to idle ---
    # Each delta tells update_animation() how much to shift self.rect
    # *after* anchoring at midbottom so the character's feet stay put.
    _compute_pivot_deltas(animations, raw_pivots, raw_frame_dims, scale)

    return animations


def _compute_pivot_deltas(animations, raw_pivots, raw_frame_dims, scale):
    """Fill ``animations[state]['pivot_delta']`` for every loaded state.

    If idle data is missing, every delta defaults to ``(0, 0)``.
    """
    if 'idle' not in raw_pivots or 'idle' not in raw_frame_dims:
        for sn in animations:
            animations[sn]['pivot_delta'] = (0, 0)
        return

    idle_px, idle_py = raw_pivots['idle']
    idle_fw, idle_fh = raw_frame_dims['idle']
    # How far idle's pivot is from idle's frame midbottom (scaled)
    idle_mb_ox = (idle_px - idle_fw / 2) * scale
    idle_mb_oy = (idle_py - idle_fh)     * scale

    for sn in animations:
        animations[sn]['idle_mb_ox'] = idle_mb_ox
        animations[sn]['idle_mb_oy'] = idle_mb_oy
        if sn in raw_pivots and sn in raw_frame_dims:
            spx, spy = raw_pivots[sn]
            sfw, sfh = raw_frame_dims[sn]
            s_mb_ox = (spx - sfw / 2) * scale
            s_mb_oy = (spy - sfh)     * scale
            animations[sn]['pivot_delta'] = (
                round(idle_mb_ox - s_mb_ox),
                round(idle_mb_oy - s_mb_oy),
            )
        else:
            animations[sn]['pivot_delta'] = (0, 0)
