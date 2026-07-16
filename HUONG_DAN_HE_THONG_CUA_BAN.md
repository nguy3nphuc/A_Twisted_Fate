# Học nhanh: Skill, VFX, Ability, rơi đồ, Poison và Menu

Mục tiêu của file này là giúp bạn lần theo **luồng code** thay vì học thuộc từng dòng.

## 1. Luồng tổng quát

```text
Quái chết
  -> cộng điểm + rơi Poison Vial + có thể rơi SkillIcon
  -> player nhặt Poison Vial
  -> poison_xp đủ mốc => Level +1, Ability Point +1
  -> pause => dùng Ability Point nâng Attack / Armor / Speed

Player nhặt SkillIcon
  -> player.skills có thêm skill và số lần dùng
  -> chọn ô skill + dùng skill
  -> trừ mana, tạo projectile/VFX/buff
  -> khi trúng quái: damage + hiệu ứng phụ (độc, slow, zombie...)
```

## 2. Skill

### Cấu hình: `config.py`

| Bạn muốn chỉnh | Vị trí | Ý nghĩa |
|---|---:|---|
| Danh sách skill | `config.py:207` — `SKILL_TYPES` | Các tên skill hợp lệ |
| Mana tốn | `config.py:190` — `SKILL_MANA_COST` | Mana mỗi lần dùng |
| Số lần dùng | `config.py:43` — `SKILL_USE_LIMITS` | `1`, `2`, `3`... |
| Damage/thời gian/tỉ lệ | `config.py:456` — `SKILL_COMBAT_CONFIG` | Nơi cân bằng từng skill |
| Tỉ lệ rơi skill | `config.py:291` — `SKILL_DROP_CONFIG` | Quái nào rơi skill gì |

### Khi người chơi dùng skill: `game.py:1310`

Hàm `use_target_skill(player)` làm 4 việc:

1. Lấy skill đang chọn trong `player.skills`.
2. Trừ mana bằng `_try_spend_player_mana(...)`.
3. Gọi skill tương ứng: ví dụ Fire gọi `_cast_fire_burst`, Dark gọi `_spawn_dark_projectile`, Thunder gọi `_cast_thunder_strike`.
4. Trừ `uses`; hết lượt dùng thì `player.skills.pop(...)` xóa skill khỏi túi.

Muốn **skill dùng nhiều lần hơn**, sửa `SKILL_USE_LIMITS` trong `config.py`.

### Khi skill trúng quái

- `game.py:1937` — `_on_player_hit_enemy_passive(...)`: hiệu ứng phụ chung.
  - Water Ball: slow + splash.
  - Wind: bleed.
  - Acid: DOT độc.
  - Fire: burn + splash.
- `game.py:1918` — `_apply_dark_hit_effects(...)`: Dark chỉ ảnh hưởng quái thường; hút máu, chuyển zombie, bonus damage.
- `game.py:2011` — `_update_enemy_dot_effects()`: mỗi frame/tick xử lý Burn, Bleed, Acid DOT.

## 3. VFX (hiệu ứng hình ảnh)

| Thành phần | Vị trí | Dùng cho |
|---|---:|---|
| `SkillEffect` | `game.py:45` | Hiệu ứng các skill như Holy, Dark, Thunder |
| `LevelUpVFX` | `game.py:151` | Chữ LEVEL UP khi lên level |
| `GigapackEffect` | `game.py:273` | Aura xanh zombie + khói khi quái spawn |
| `SymbolVFX` | `game.py` (trước `GigapackEffect`) | Crown boss, alert/warning symbol |

Hàm nhanh để tạo hiệu ứng skill là `game.py:1369`:

```python
self._spawn_skill_vfx('holy', x, y, facing)
```

VFX mới nên được thêm cấu hình/path, cắt frame, rồi đưa sprite vào `self.effects`.

## 4. Zombie của Dark

- Điều kiện quái nhỏ: `_is_dark_eligible_enemy(...)` trong `game.py`.
- Chuyển zombie: `_apply_dark_hit_effects(...)`.
- AI zombie: `_update_zombie_enemy(...)` trong `game.py`.
- Aura nhận biết: `GigapackEffect('zombie_aura', target=enemy, loop=True)`.

Chỉ số zombie nằm trong `config.py:SKILL_COMBAT_CONFIG['dark']`:

```python
'zombie_duration_ms'       # thời gian zombie
'zombie_attack_damage'      # sát thương đánh đồng loại
'zombie_attack_interval_ms' # nhịp đánh
'zombie_move_multiplier'    # tốc độ di chuyển
```

## 5. Rơi đồ và Poison EXP

### Sprite item

- `entities.py:4195` — `AbilityVial`: bình Poison EXP.
- `entities.py:4256` — `SkillIcon`: item skill nhặt được.

### Quái chết

Đoạn xử lý nằm trong `game.py:3853` trở xuống:

1. `team_score_awarded`: cộng điểm đúng một lần.
2. `dropped_ability_vial`: rơi Poison Vial.
3. `dropped_skill`: roll SkillIcon.

Các cờ `dropped_*` rất quan trọng: chúng ngăn quái chết rơi item lặp lại mỗi frame.

### Chỉnh Poison

| Cấu hình | Vị trí | Ý nghĩa |
|---|---:|---|
| `ABILITY_VIAL_DROP_CHANCE` | `config.py:230` | Xác suất rơi bình |
| `POISON_LEVEL_BASE_REQUIRED` | `config.py:231` | EXP cần cho level đầu |
| `POISON_LEVEL_REQUIREMENT_PER_LEVEL` | `config.py:232` | Độ khó tăng mỗi level |
| `POISON_VIAL_DROP_COUNT` | `config.py:234` | Quái mạnh rơi nhiều bình hơn |

`game.py:1193` — `_poison_drop_count(enemy)` chọn số bình theo loại quái.

## 6. Level và Ability

### Dữ liệu player

`game.py:1175` — `_ensure_player_abilities(player)` tạo các biến:

```python
player.level
player.poison_xp
player.ability_points
player.ability_levels = {'attack': 0, 'armor': 0, 'speed': 0}
```

### Nhặt bình và lên level

Ở `game.py:3916`:

```python
player.poison_xp += vial.poison_xp
while player.poison_xp >= required:
    player.level += 1
    player.ability_points += 1
```

Khi level tăng, `LevelUpVFX` được thêm vào `self.effects`.

### Chỉnh sức mạnh một level

Sửa trong `config.py`:

```python
ABILITY_ATTACK_BONUS_PER_LEVEL = 3
ABILITY_ARMOR_BONUS_PER_LEVEL = 12
ABILITY_SPEED_BONUS_PER_LEVEL = 0.35
```

Ability panel pause được vẽ ở `game.py` quanh dòng `4340`.

## 7. Menu

File duy nhất điều khiển menu là `menu.py` ở thư mục gốc.

| Phần | Vị trí | Ý nghĩa |
|---|---:|---|
| Asset folder | `menu.py:22` — `MENU_DIR` | Hiện là `assets/menu` |
| Button frame + chữ | `menu.py:91` — `FrameButton` | Ảnh frame, chữ render bằng font |
| Menu state | `menu.py:124` — `MainMenu` | MAIN, mở sách, PLAY/BACK |
| Video mở sách | `menu.py:167` — `_load_video()` | Đọc `open_book.mp4` |
| Avatar P1/P2 | `menu.py:265` — `_draw_player_avatars()` | Vẽ hai avatar lên sách mở |

Luồng menu:

```text
main.py -> MainMenu.run()
START GAME -> mở sách
PLAY -> trả lựa chọn cho main.py
main.py -> Game.start_campaign() -> phase 1
BACK -> MAIN / CLOSED (trạng thái ban đầu)
```

## 8. Cách học nhanh nhất

1. Muốn **đổi số**: tìm trong `config.py` trước.
2. Muốn hiểu **một feature chạy ra sao**: tìm hàm có tên hành động trong `game.py`.
3. Muốn thêm **sprite/item**: xem class tương ứng trong `entities.py`.
4. Muốn thêm **hiệu ứng**: xem `SkillEffect` hoặc `GigapackEffect` trong `game.py`.
5. Sau khi sửa Python, chạy:

```powershell
python -m py_compile game.py entities.py config.py menu.py
```
