# BÁO CÁO ĐỒ ÁN LẬP TRÌNH HƯỚNG ĐỐI TƯỢNG

## Xây dựng trò chơi hành động 2 người chơi bằng Python và Pygame


## Lời mở đầu

Trong quá trình học lập trình hướng đối tượng, việc áp dụng các khái niệm như lớp, đối tượng, kế thừa, đóng gói và đa hình vào một sản phẩm cụ thể giúp sinh viên hiểu rõ hơn cách tổ chức chương trình. Vì vậy, em thực hiện đồ án **trò chơi hành động 2 người chơi** bằng ngôn ngữ Python và thư viện Pygame.

Trò chơi cho phép hai người chơi cùng chiến đấu với quái vật, sử dụng đòn đánh thường, kỹ năng, ultimate, nhặt vật phẩm, tăng cấp và hoàn thành các màn chơi. Bên cạnh gameplay, đồ án tập trung áp dụng tư duy OOP để tách các đối tượng trong game thành các lớp có trách nhiệm rõ ràng, giúp mã nguồn dễ đọc, bảo trì và mở rộng.

Trong quá trình thực hiện, em đã xây dựng hệ thống nhân vật Knight và Archer, quái vật/Boss, animation, va chạm, bản đồ, kỹ năng, hiệu ứng hình ảnh, menu, điểm số và hệ thống tăng cấp. Báo cáo này trình bày mục tiêu, cách thiết kế, các chức năng chính, kết quả đạt được và hướng phát triển trong tương lai.

---

# CHƯƠNG 1. TỔNG QUAN ĐỀ TÀI

## 1.1. Lý do chọn đề tài

Game là một môi trường phù hợp để áp dụng lập trình hướng đối tượng vì trong game có nhiều thực thể riêng biệt: người chơi, quái vật, đạn, vật phẩm, kỹ năng và hiệu ứng. Mỗi thực thể có dữ liệu và hành vi riêng nhưng vẫn có các điểm chung. Do đó, đề tài giúp minh họa trực quan các nguyên lý OOP và tạo ra một sản phẩm có thể chơi được.

## 1.2. Mục tiêu

- Xây dựng game 2 người chơi bằng Python và Pygame.
- Áp dụng các nguyên lý lập trình hướng đối tượng.
- Tạo hệ thống chiến đấu gồm tấn công thường, đạn, kỹ năng và ultimate.
- Xây dựng quái vật có AI, Boss, điểm số và chuyển màn.
- Tạo bản đồ có va chạm, tầng, cầu thang, đường hầm và camera động.
- Tạo menu, giao diện HUD, pause và hệ thống tăng cấp nhân vật.

## 1.3. Công nghệ sử dụng

| Thành phần | Công nghệ / công cụ |
|---|---|
| Ngôn ngữ | Python 3 |
| Thư viện game | Pygame |
| Dữ liệu animation | JSON |
| Đồ họa | Pixel art, spritesheet, VFX spritesheet |
| Công cụ nội bộ | `box_tool.py`, `pivot_tool.py`, `skill_ui_tuner.py`, `pixel_ruins_tuner.py` |

## 1.4. Phạm vi đề tài

Đồ án tập trung vào một game chạy trên máy tính, điều khiển bằng bàn phím, có hai người chơi trên cùng một màn hình. Game gồm nhiều màn, trong đó người chơi tiêu diệt quái để nhận điểm; đạt đủ điểm sẽ chuyển sang màn tiếp theo.

---

# CHƯƠNG 2. PHÂN TÍCH VÀ THIẾT KẾ HỆ THỐNG

## 2.1. Kiến trúc mã nguồn

| File | Vai trò chính |
|---|---|
| `main.py` | Điểm khởi động game chính, mở menu trước khi vào game. |
| `test.py` | Chạy chế độ thử nghiệm, phù hợp kiểm tra gameplay/debug. |
| `game.py` | Vòng lặp game, xử lý input, va chạm, spawn, điểm, skill, HUD và chuyển màn. |
| `entities.py` | Các lớp nhân vật, quái vật, đạn, hitbox, vật phẩm. |
| `sprites.py` | Đọc spritesheet, cắt frame và điều khiển animation. |
| `config.py` | Các hằng số để cân bằng game: máu, damage, tốc độ, cooldown, điểm. |
| `menu.py` | Menu mở game, trạng thái đóng/mở sách, Play/Back/Quit. |
| `assets/animation_metadata.json` | Thông tin số frame, tốc độ animation, pivot và hitbox. |
| `assets/maps/pixel_ruins_layout.json` | Dữ liệu map, collider, tunnel, floor, cầu thang. |

## 2.2. Sơ đồ các đối tượng chính

```text
pygame.sprite.Sprite
        │
        ├── Knight
        ├── Archer
        ├── Lizardman / Cyclop / Kobold / ...
        ├── Boss
        ├── Projectile
        ├── AttackHitbox
        └── Item (Potion, AbilityVial, SkillIcon, ...)

HealthMixin
        │
        ├── Player
        ├── Enemy
        └── Boss
```

`pygame.sprite.Sprite` hỗ trợ quản lý đối tượng bằng các group của Pygame. `HealthMixin` cung cấp thuộc tính và hành vi chung liên quan đến máu, giáp, mana và nhận sát thương.

## 2.3. Áp dụng lập trình hướng đối tượng

### Đóng gói

Mỗi class tự quản lý dữ liệu và hành vi của mình. Ví dụ `Archer` quản lý tốc độ, hướng nhìn, dash, loại mũi tên, animation và hàm `spawn_arrow()`.

### Kế thừa

Các thực thể game kế thừa từ `pygame.sprite.Sprite`. Nhân vật và quái có thể dùng `HealthMixin` để tái sử dụng logic máu/giáp/mana.

### Đa hình

Mỗi nhân vật có thể có hàm `update()` và `take_damage()` riêng. Vòng lặp trong `game.py` gọi cùng một kiểu xử lý, nhưng Knight, Archer hoặc từng loại quái sẽ thực hiện hành vi phù hợp với class của chúng.

### Trừu tượng hóa

Các phần phức tạp như animation, va chạm, skill và map được gom thành hàm/lớp riêng. Nhờ đó, vòng lặp game chính không phải chứa toàn bộ chi tiết cài đặt.

---

# CHƯƠNG 3. CÁC CHỨC NĂNG ĐÃ XÂY DỰNG

## 3.1. Nhân vật người chơi

Game có hai nhân vật:

- **Knight (P1):** đánh cận chiến, combo, phòng thủ và ultimate gây sát thương diện rộng.
- **Archer (P2):** bắn xa, dash, đổi loại mũi tên và ultimate dạng tia/bắn xuyên.

Mỗi nhân vật có các thuộc tính cơ bản: HP, armor, mana, tốc độ, damage, animation, footbox để di chuyển và hurtbox để nhận sát thương.

## 3.2. Hệ thống chiến đấu

- Đòn đánh thường tạo `AttackHitbox` hoặc projectile.
- Hitbox kiểm tra giao nhau với `hurtbox` của mục tiêu.
- Damage được tính sau khi xét armor, chí mạng và các hiệu ứng phụ.
- Khi trúng đòn, game tạo số sát thương và hiệu ứng hình ảnh.
- Ultimate của Knight tạo shockwave; ultimate của Archer tạo beam/projectile theo thiết kế.

## 3.3. Mũi tên của Archer

Archer có thể đổi loại mũi tên bằng phím đã gán. Mỗi loại mũi tên có tác dụng khác nhau, ví dụ sát thương cơ bản, làm chậm, lan sát thương hoặc hiệu ứng nguyên tố. Cấu hình cân bằng của mũi tên được đặt trong `config.py`.

## 3.4. Kỹ năng và hiệu ứng VFX

Kỹ năng nhặt được được lưu trong danh sách `player.skills`. Khi người chơi chọn và dùng skill, game kiểm tra mana trước bằng hàm `_try_spend_player_mana()`.

Các kỹ năng gồm những hiệu ứng như Holy, Dark, Thunder, Water, Wind, Wood và Zombie. VFX được đọc từ spritesheet và vẽ trước/sau nhân vật tùy loại hiệu ứng để bảo đảm thứ tự hiển thị hợp lý.

## 3.5. Quái vật, Boss và AI

- Quái vật tìm mục tiêu và di chuyển/đánh người chơi.
- Một số quái có animation, tầm đánh, tốc độ và hành vi riêng.
- Boss có máu cao hơn, animation riêng, điểm thưởng lớn hơn.
- Zombie là quái bị chuyển đổi bởi Dark; nó sẽ tấn công các quái khác thay vì người chơi.

## 3.6. Vật phẩm, Poison và tăng cấp

Khi quái chết, game tạo vật phẩm rơi ra. Poison vial có tỉ lệ rơi 100%; quái mạnh rơi nhiều vial hơn. Người chơi nhặt vial để nhận EXP. Khi đủ EXP, nhân vật tăng level, nhận điểm ability và có thể tăng các chỉ số:

- Attack: tăng sát thương.
- Armor: tăng giáp tối đa.
- Speed: tăng tốc độ di chuyển.

Giao diện pause hiển thị level, số poison vial, điểm ability và phím nâng cấp của P1/P2.

## 3.7. Bản đồ và va chạm

Map màn 4 sử dụng dữ liệu từ `pixel_ruins_layout.json`. Dữ liệu gồm:

- Vùng va chạm không cho nhân vật đi qua.
- Viền map dạng line.
- Vùng tunnel, line đầu/cuối tunnel.
- Cầu thang có bounding box và hai line đầu/cuối.
- Vùng tầng để xác định nhân vật đang ở tầng nào.

Nhân vật chỉ đi vào tunnel sau khi cắt qua line đầu/cuối. Khi ở tunnel, nhân vật được làm mờ để thể hiện đang ở dưới lớp bản đồ. Hệ thống floor cũng hỗ trợ giới hạn việc bắn từ tầng trên xuống tầng dưới gần kề.

## 3.8. A* Pathfinding

Quái ở map lớn sử dụng A* để tìm đường. Thuật toán chia map thành lưới, tránh collider và tìm đường ngắn đến mục tiêu. Các đường đi có thể được tái sử dụng/nối vào mạng đường đã có để giảm số lần tính toán và hạn chế lag.

## 3.9. Menu, Pause và HUD

- Menu mở đầu có Start Game và Quit.
- Khi mở sách, người chơi chọn Play hoặc Back; hai bên trang có avatar của P1/P2.
- Phím `ESC` pause game, giao diện dùng nền dạng cuộn giấy.
- HUD hiển thị HP, armor, mana, điểm đội, đồng hồ, mũi tên đang dùng và ô ultimate.

## 3.10. Điểm số và chuyển màn

Mỗi quái bị hạ sẽ cộng điểm đội. Boss cho số điểm cao hơn quái thường. Khi đội đạt 1000 điểm trong màn, game chuyển sang màn tiếp theo. Chế độ campaign đi từ màn 1 đến màn 4.

---

# CHƯƠNG 4. HƯỚNG DẪN CHẠY VÀ KIỂM THỬ

## 4.1. Cài đặt

```powershell
pip install pygame
```

## 4.2. Chạy game

```powershell
python main.py
```

Chế độ kiểm thử:

```powershell
python test.py
```

## 4.3. Kiểm thử chính

| Chức năng | Kết quả mong đợi |
|---|---|
| Di chuyển | P1 và P2 di chuyển theo phím được gán. |
| Đánh thường | Tạo hitbox/đạn và trừ máu mục tiêu khi va chạm. |
| Đổi mũi tên | Archer thay loại mũi tên và HUD cập nhật icon. |
| Nhặt poison | Vial biến mất, EXP tăng và có thể lên level. |
| Pause | ESC mở/đóng giao diện cuộn giấy và dừng gameplay. |
| Tunnel | Đi qua line đầu/cuối để vào hầm, nhân vật bị làm mờ. |
| Chuyển màn | Đạt mốc điểm đội sẽ sang màn tiếp theo. |

---

# CHƯƠNG 5. KẾT QUẢ VÀ ĐÁNH GIÁ

## 5.1. Kết quả đạt được

Đồ án đã xây dựng được game 2 người chơi có thể chạy và chơi được. Các chức năng chính như chiến đấu, quái vật, kỹ năng, vật phẩm, tăng cấp, map có va chạm, menu, pause và chuyển màn đã được tích hợp.

Mã nguồn được chia theo trách nhiệm: `entities.py` quản lý thực thể, `game.py` điều phối gameplay, `sprites.py` xử lý animation và `config.py` tập trung các thông số cân bằng. Cách tổ chức này giúp việc sửa một chỉ số hoặc thêm tính năng mới thuận tiện hơn.

## 5.2. Hạn chế

- AI quái vật vẫn có thể cần tối ưu thêm khi số lượng quái lớn.
- Cân bằng damage, tốc độ, mana và skill cần tiếp tục thử nghiệm.
- Map hiện cần đánh dấu thủ công collider, tầng và tunnel bằng tuner.
- Chưa có lưu tiến trình, âm thanh hoàn chỉnh hoặc hệ thống nhiều người chơi qua mạng.

## 5.3. Hướng phát triển

- Thêm nhiều màn chơi, boss và loại quái mới.
- Thêm âm thanh, nhạc nền và cài đặt âm lượng.
- Lưu level, ability và tiến trình campaign.
- Thêm nhiều class nhân vật và cây kỹ năng.
- Tối ưu A* và spawn quái khi game có nhiều thực thể.
- Bổ sung màn hình hướng dẫn điều khiển và cài đặt game.

---

# KẾT LUẬN

Đồ án đã hoàn thành mục tiêu xây dựng một trò chơi hành động 2 người chơi bằng Python và Pygame, đồng thời vận dụng các nguyên lý lập trình hướng đối tượng trong quá trình phát triển. Qua đồ án, em hiểu rõ hơn cách phân tích bài toán, thiết kế class, quản lý animation, xử lý va chạm, tổ chức dữ liệu và phát triển một chương trình có nhiều thành phần tương tác với nhau.

Trong tương lai, đồ án có thể tiếp tục được mở rộng bằng cách tối ưu AI, bổ sung nội dung game, cải thiện cân bằng và hoàn thiện trải nghiệm người chơi. Đây là nền tảng để em tiếp tục nghiên cứu sâu hơn về lập trình game và phát triển phần mềm hướng đối tượng.

---

# PHỤ LỤC: GỢI Ý ẢNH CHỤP ĐỂ ĐƯA VÀO BÁO CÁO

1. Màn hình menu lúc chưa mở sách.
2. Màn hình chọn Play/Back với avatar hai nhân vật.
3. Một màn chiến đấu có Knight, Archer và quái.
4. HUD gồm HP, armor, mana, ultimate và điểm đội.
5. Pause menu có bảng level/ability.
6. Archer đổi loại mũi tên.
7. Hiệu ứng skill Holy, Dark, Thunder hoặc Zombie.
8. Pixel Ruins map với collider/tunnel/floor ở chế độ debug.
9. Boss xuất hiện và cảnh báo Boss.
10. Màn hình hoàn thành một màn hoặc chuyển màn.

---

# PHỤ LỤC 2: DANH SÁCH CLASS VÀ HÀM CỦA CHARACTER

Phụ lục này liệt kê các class liên quan trực tiếp đến nhân vật người chơi, quái thường và Boss trong file `entities.py`. Các hàm bắt đầu bằng dấu gạch dưới (`_`) là hàm nội bộ, phục vụ cho class đó.

## A. Class dùng chung cho nhân vật

### `HealthMixin`

Hỗ trợ dữ liệu máu, giáp, mana và xử lý nhận sát thương cho các thực thể có HP.

```text
__init__
_ensure_health_bar
take_damage
on_death
_get_true_pivot
```

## B. Character người chơi

### `Knight`

```text
__init__
foot_y
_is_control_pressed
load_assets
_apply_frame
_update_hurtbox
take_damage
update
handle_input
start_combo_step
spawn_attack_hitbox
_spawn_ultimate_shockwave
on_death
```

### `Archer`

```text
__init__
foot_y
_is_control_pressed
load_assets
_apply_frame
_update_hurtbox
_clamp_position
take_damage
update
handle_input
spawn_arrow
cycle_arrow_type
_spawn_ultimate_beam
on_death
```

## C. Quái thường

### `Lizardman`

```text
__init__, foot_y, load_assets, take_damage, update, update_animation
_apply_alpha, _update_hurtbox, _spawn_enemy_attack_hitbox, on_death
```

### `Cyclop`

```text
__init__, foot_y, load_assets, take_damage, update, update_animation
_apply_alpha, _update_hurtbox, _spawn_enemy_attack_hitbox, on_death
```

### `Kobold`

```text
__init__, foot_y, load_assets, take_damage, update, update_animation
_apply_alpha, _update_hurtbox, _spawn_enemy_attack_hitbox, on_death
```

### `Fireworm`

```text
__init__, foot_y, load_assets, take_damage, update, update_animation
_apply_alpha, _update_hurtbox, on_death
```

### `GoblinWarrior`

```text
__init__, foot_y, load_assets, take_damage, update, update_animation
_apply_alpha, _update_hurtbox, _spawn_enemy_attack_hitbox, on_death
```

### `GoblinSpearman`

```text
__init__, foot_y, load_assets, take_damage, update, update_animation
_apply_alpha, _update_hurtbox, on_death
```

### `GoblinTank`

```text
__init__, foot_y, load_assets, take_damage, update, update_animation
_apply_alpha, _update_hurtbox, _spawn_enemy_attack_hitbox, on_death
```

## D. Boss

### `FatCultist`

```text
__init__
foot_y
_get_true_pivot
update
_update_ai
_spawn_enemy_attack_hitbox
_update_visuals
_update_hurtbox
take_damage
on_death
```

### `DeathBringer`

```text
__init__
foot_y
_get_true_pivot
update
_update_ai
_spawn_enemy_attack_hitbox
_update_visuals
_update_hurtbox
take_damage
on_death
```

## E. Đạn và đối tượng chiến đấu liên quan character

| Class | Hàm |
|---|---|
| `AttackHitbox` | `__init__`, `update` |
| `KnightUltimateShockwave` | `__init__`, `floor_y`, `can_hit`, `collides_with`, `register_hit`, `update` |
| `Arrow` | `__init__`, `y`, `floor_y`, `update` |
| `Fireball` | `__init__`, `y`, `floor_y`, `update` |
| `Spear` | `__init__`, `y`, `floor_y`, `update` |
| `DeathBringerSpell` | `__init__`, `update` |

## F. Ý nghĩa những hàm xuất hiện nhiều lần

| Hàm | Ý nghĩa |
|---|---|
| `__init__` | Khởi tạo dữ liệu của object. |
| `update` | Cập nhật object trong mỗi frame game. |
| `take_damage` | Nhận sát thương, trừ HP và xử lý trạng thái bị đánh/chết. |
| `on_death` | Chuyển sang trạng thái chết. |
| `load_assets` | Đọc asset và animation của character. |
| `update_animation` | Cập nhật frame animation của quái. |
| `_apply_frame` / `_update_visuals` | Đổi ảnh frame hiện tại và căn vị trí hiển thị. |
| `_update_hurtbox` | Cập nhật vùng nhận sát thương theo vị trí chân nhân vật. |
| `_spawn_enemy_attack_hitbox` | Tạo vùng đánh của quái. |
| `spawn_attack_hitbox` | Tạo vùng đánh thường của Knight. |
| `spawn_arrow` | Tạo mũi tên của Archer. |
