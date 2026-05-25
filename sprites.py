import pygame
import os


class SpriteSheet:
    def __init__(self, filename):
        try:
            self.sheet = pygame.image.load(filename).convert_alpha()
        except Exception:
            self.sheet = None

    def image_at(self, rectangle, colorkey=None):
        # rectangle: x,y,w,h
        if self.sheet is None:
            surf = pygame.Surface((rectangle[2], rectangle[3]), pygame.SRCALPHA)
            surf.fill((255, 0, 255, 255))
            return surf
        rect = pygame.Rect(rectangle)
        image = pygame.Surface(rect.size, pygame.SRCALPHA)
        image.blit(self.sheet, (0, 0), rect)
        return image

    def load_strip(self, rect, image_count, colorkey=None):
        frames = []
        x, y, w, h = rect
        for i in range(image_count):
            frames.append(self.image_at((x + i * w, y, w, h), colorkey))
        return frames


class Animator:
    """Simple state-based animator.
    states_frames: dict of state -> list of Surface frames
    durations: dict of state -> frame duration in ms
    """
    def __init__(self, states_frames, durations=None, default_state=None, loop_states=None):
        self.states = states_frames
        self.durations = durations or {}
        self.loop_states = loop_states or set()
        self.state = default_state or next(iter(states_frames))
        self.frame_index = 0
        self.time = 0
        self.finished = False

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

    def is_midpoint(self):
        frames = self.states[self.state]
        return self.frame_index == len(frames) // 2

    def is_finished(self):
        return self.finished


def get_frame_dimensions(filepath, w, h):
    path_lower = filepath.replace('\\', '/').lower()
    filename = os.path.basename(path_lower)
    
    # New trimmed Knight sprites
    if 'knight' in path_lower:
        if 'attack 1' in filename:
            return 59, 34
        elif 'attack 2' in filename:
            return 50, 32
        elif 'attack 3' in filename:
            return 55, 44
        elif 'death' in filename:
            return 54, 33
        elif 'defend' in filename:
            return 34, 34
        elif 'hurt' in filename:
            return 30, 34
        elif 'idle' in filename:
            # 210x35 -> 7 frames: 30x35
            return 30, 35
        elif 'run' in filename:
            # 336x36 -> 8 frames: 42
            return 42, 36
        return 96, 84  # Fallback

    if 'archer' in path_lower:
        if 'attack' in filename:
            return 48, 39      # 624/48 = 13 frames
        elif 'idle' in filename:
            return 27, 40      # 216/27 = 8 frames
        elif 'run' in filename:
            return 44, 35      # 352/44 = 8 frames
        elif 'dash' in filename:
            return 38, 42      # 418/38 = 11 frames
        elif 'hurt' in filename:
            return 31, 39      # 124/31 = 4 frames
        elif 'death' in filename:
            return 62, 39      # 1240/62 = 20 frames
        return 64, 64

    
    # Skeleton sprites
    if 'skeleton' in path_lower or 'skeleton' in filename:
        if 'walk' in filename:
            return 22, 33
        elif 'idle' in filename:
            return 24, 32
        elif 'hit' in filename:
            return 30, 32
        elif 'dead' in filename:
            return 33, 32
        elif 'attack' in filename:
            return 43, 37

    # Default fallback: if height divides width perfectly, assume square frames
    if h > 0 and w % h == 0 and (w // h) > 1:
        return h, h
    return w, h


def load_frames_from_folder(folder, basename, scale=1.0):
    """Load frames from files in `folder` that match basename (case-insensitive).
    Returns a list of Surfaces sorted by filename.
    """
    if not os.path.isdir(folder):
        return []

    # Map common aliases/synonyms
    aliases = {
        'run': ['run', 'walk'],
        'idle': ['idle'],
        'attack': ['attack'],
        'hit': ['hit', 'hurt'],
        'death': ['death', 'dead'],
    }

    search_terms = aliases.get(basename.lower(), [basename.lower()])

    files = []
    for fn in os.listdir(folder):
        name, ext = os.path.splitext(fn)
        if ext.lower() not in ('.png', '.jpg', '.jpeg', '.bmp'):
            continue
        # Check if any of the search terms is in the file name
        matched = False
        for term in search_terms:
            if term in name.lower():
                matched = True
                break
        if matched:
            files.append(fn)

    files.sort()
    frames = []
    for fn in files:
        path = os.path.join(folder, fn)
        try:
            img = pygame.image.load(path).convert_alpha()
        except Exception:
            img = pygame.Surface((64, 64), pygame.SRCALPHA)

        w, h = img.get_width(), img.get_height()
        fw, fh = get_frame_dimensions(path, w, h)

        # Split horizontal/vertical strip using detected frame width and height
        if fw > 0 and fh > 0 and w >= fw:
            cols = w // fw
            rows = h // fh
            for r in range(rows):
                for c in range(cols):
                    sub = pygame.Surface((fw, fh), pygame.SRCALPHA)
                    sub.blit(img, (0, 0), (c * fw, r * fh, fw, fh))
                    if scale != 1.0:
                        sub = pygame.transform.scale(sub, (int(fw * scale), int(fh * scale)))
                    frames.append(sub)
        else:
            if scale != 1.0:
                img = pygame.transform.scale(img, (int(w * scale), int(h * scale)))
            frames.append(img)

    return frames
