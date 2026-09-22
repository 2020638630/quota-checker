# 桌宠素材接入交接说明

> 给下一个接手的 AI/开发者：这份文档自包含，读完即可继续工作。

## 1. 项目是什么

`<project-root>` 是一个 Windows 桌面小工具：定时查询 DeepSeek API 余额，弹出一个 Q 版鲸鱼娘女仆桌宠（tkinter），她会在屏幕上走路、坐下来敲键盘、余额低时提醒。

主程序：`quota_pet.py`（纯标准库运行时，Python 3.12+）。
启动：双击 `启动桌宠.bat`，或 `python quota_pet.py`。

## 2. 当前角色素材状态

角色是 **DeepSeek 鲸鱼娘 Q 版女仆**：深蓝长发+呆毛、白蕾丝女仆头饰+亮蓝蝴蝶结、发侧白鲸鱼鳍、蓝眼、深蓝女仆裙+白围裙（围裙小鲸鱼图案）、深蓝小皮鞋。

素材已接入并可用（用户验收"没大问题"）：
- `pet_assets/front.png` — 正面，双手搭迷你键盘
- `pet_assets/front_typing.png` — 正面抬手帧（打字动画交替）
- `pet_assets/side_l.png` / `side_l_1.png` — 左侧面走路两帧（Runtime 会交替播放）
- `pet_assets/side_r.png` / `side_r_1.png` — 右侧面两帧（由左侧镜像生成）
- `pet_assets/back.png` — 背面
- `pet_assets/manifest.json` — 可选素材 manifest；缺失时回退到旧固定文件名
- 色键：`KEY = "#ff00fe"`（RGB 255,0,254），tkinter `-transparentcolor` 精确匹配透明

代码侧关键开关：`quota_pet.py` 里 `SELF_CONTAINED = True`——front 是整图（身体+键盘+手一体），不叠加 keyboard/arm/hand 分层。走路帧在 `_walk_step` 里按 `(left//3)%2` 交替；打字在 `_key_tick` 里切 front / front_typing。

## 3. 文件结构

```
quota-checker/
├── quota_pet.py        # 桌宠主程序
├── quota.py / quota_widget.py / mascot.py / pngtool.py
├── README.md
├── 启动桌宠.bat / 关闭桌宠.bat / start-pet.bat / stop-pet.bat
├── data/               # 运行数据：history.json, quotas.json, ui.json, usage.json
├── pet_assets/         # 运行素材（色键抠图用，200px 宽左右）
│   ├── front / front_typing / side_l / side_l_1 / side_r / side_r_1 / back
│   ├── blink_1 / blink_2 / sleep_1 / sleep_2  # 可选动作帧
│   ├── manifest.json                          # 可选动作素材映射
│   ├── keyboard / arm_l / arm_r / hand / hand_up / keys_map.json  # 旧分层，SELF_CONTAINED 下不参与运行
├── source/             # 高清原图（2048，AI 生成，品红/红底）
│   ├── _core_front.png      正面主帧
│   ├── _new_typing.png      抬手帧
│   ├── _new_side1.png       侧面走路帧1
│   ├── _new_side2.png       侧面走路帧2
│   └── _new_back.png        背面
└── tools/              # 素材处理脚本（历史遗留，可参考）
```

## 4. 素材处理流程（最重要，照做就不会再翻车）

从 `source/` 高清原图到 `pet_assets/` 小图，统一流程：

1. **背景识别**：取四角像素均值当背景色（这批原图背景是红色品红 ~ (235,110,100)），到大图背景色距离 < 90 的像素 → 纯 `(255,0,254)`。
2. **裁剪 bbox**：包围所有非品红像素。
3. **NEAREST 等比缩放**到目标宽（正面 200、侧背 180）。**绝不能用 LANCZOS/BILINEAR**——插值会把角色边缘和品红混成中间色，色键抠不掉变成粉边。
4. **洪水填充硬边**：从四角 BFS，"距离品红 < 160"的像素全压成纯品红；角色内部不连通的品红洞填肤色 `(254,220,200)`。
5. **删外扩块**（仅这批图需要）：正面两侧浅肤色外扩、键盘下方横条、侧面长发中间小块——按位置+肤色判定删除。

参考实现见对话中用过的脚本逻辑（在 `tools/` 和历史 `_rebuild_*.py`）。

## 5. 血泪教训（务必读）

- **AI 图天然柔边**，色键素材要求硬边。唯一可靠的是「NEAREST 不插值 + 洪水填充吃边缘」，不是猜颜色阈值。
- **不要在小图上反复打补丁**。脸颊洞、腿缝、脖子那块，每次局部修补都误伤周围正常像素，越修越坏。出问题就回 `source/` 原图重跑整条流程，别在 `pet_assets/` 上硬改。
- **腮红/肤色离品红近**（如 (255,95,150) 距品红 141），会被洪水填充阈值误吃。腮红颜色要选离品红远的（B 分量小，如 (255,40,80)）。
- **窗口高度按所有帧最大值开**，否则走路高帧的腿被裁掉。`quota_pet.py` 已改成 `max(im.height() for im in self.scaled.values())`。
- 桌宠进程用 `python quota_pet.py` 启动，调试前先按命令行匹配 `quota_pet` 杀掉旧进程。

## 6. 已知遗留小问题（用户接受，别再修）

- 正面脖子下方有一小条 AI 原生的深色阴影，小尺寸不明显，**不要再补**——越补越糟。
- 正面两侧头发边缘可能有极淡的外扩色残点，用户已说"先这样"。
- 走路两帧是 AI 分别生成的，身体大体对齐，细看有轻微抖动。

## 7. 后续加素材怎么做

要加新动作（眨眼、表情、更多走路帧、转身、闲置动作）：

1. 用 `image_edit` 基于 `source/_core_front.png`（或对应角度原图）生成新帧，prompt 强调「纯品红背景、赛璐璐硬边、实心填充、保持角色一致」。
2. 下载新图到 `source/`。
3. 按第 4 节流程处理到 `pet_assets/`，保持文件名和尺寸比例一致。
4. 在 `pet_assets/manifest.json` 中填写新帧；blink/sleep 文件不存在时会自动退化为无该动作。
5. 两帧动画要求：同一 bbox、等比缩放到同尺寸、身体像素对齐，只动要动的部位。

## 8. 不要做的事

- 不要用 LANCZOS 缩放色键素材。
- 不要把 `.py` 挪进子目录（互相 import，且用 `__file__` 定位 `pet_assets/` 和 `data/`）。
- `SELF_CONTAINED = True` 时旧 keyboard/arm/hand 分层不参与运行；只有切回分层模式时才需要保留它们。
- 不要在 `pet_assets/` 小图上反复局部修补——有问题回 `source/` 重跑流程。
