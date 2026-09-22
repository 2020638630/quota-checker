# quota-checker — DeepSeek 余额便携查询（桌宠 + 桌面挂件 + CLI）

个人自用版：内置只保留 **DeepSeek**，其他家通过 `custom` 通道按需接入。

## 🐋 鲸鱼娘桌宠（推荐）

```bash
python quota_pet.py
```

透明置顶桌宠，**点一下摸头就报余额**：

- 三视图行走（左右散步用侧视图自动镜像）、发呆呼吸、拖拽移动
- **⌨ 键盘互动**：你敲键盘，她跟着敲——全局轮询按键（`GetAsyncKeyState`），手随键抬起落下、键帽跟着点亮；键盘与手是程序自绘素材（`pet_assets/make_keyboard.py`），不依赖任何外部美术资源
- **🐋 增殖**：挂机 90 秒不动 → 自动复制出一只小号本体（上限 8 只防刷屏）；右键菜单也可手动 "增殖一只"
- **单击** → 弹出余额气泡（圆角白底深蓝描边，余额 + 赠送/充值拆分）
- 余额低于 ¥10 时气泡转红色告警 + 桌宠抖一下
- 每 10 分钟自动刷新；余额变化时主动冒泡提醒
- **多屏安全**：气泡跟着她走（120ms 跟随），跨屏不跑回主屏；贴顶自动翻到下方；行走边界用虚拟桌面（vroot）判定——`winfo_screenwidth` 只有主屏宽度，是跨屏 bug 的根源
- **右键菜单**：看看余额 / 刷新余额 / **🔑 配置 DeepSeek Key** / 自动刷新开关 / 尺寸切换(小/中) / 增殖一只 / 键盘互动开关 / 置顶开关 / 退出

### 配置 Key（桌宠自带界面）

右键桌宠 → **🔑 配置 DeepSeek Key…**，弹出的窗口里：

- 填 Key（默认打码，可勾"显示"；已设 `DEEPSEEK_API_KEY` 环境变量时留空即用）
- 点 **测试连通性** 立即验证——成功显示实时余额，失败会区分"Key 无效(401)"等具体原因
- 可调**余额告警阈值**（低于该值气泡变红、她抖一下）
- 保存时经 DPAPI 加密写入 quotas.json，并**同步给所有增殖体**、立即刷新

桌宠与桌面挂件共用同一个 `quotas.json`，两边配置互通。

### 素材与授权（重要）

- 鲸鱼娘「大肥鱼」三视图素材来自 **[1190fasheqi/dafeiyu-pet](https://github.com/1190fasheqi/dafeiyu-pet)（MIT License）**，是 DeepSeek V4 Pro 的社区二创形象。**仓库里只保留预处理后的成品** `pet_assets/*.png`；原始立绘和上游源码属于下载产物，已清理——需要改素材时从上游重新下载到 `_assets/sprites/` 即可
- 气泡样式参考 **[MeteorNOX/DeepSeek-Balance-Whale-Widget](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget)（MIT License）**
- 素材重建（纯标准库，无需 Pillow）：
  - 立绘：把上游的 `{正面,侧面,背面}_187.png` 放到 `_assets/sprites/`，运行 `python tools/build_sprites.py` 生成立绘四态
  - 键盘与手：`python tools/make_keyboard.py`（程序自绘，无外部依赖）
  - 为什么要处理：Windows 的 tkinter 只能用色键透明，软边 alpha 会渗粉边，所以 alpha 需二值化成硬边；镜像素材也在此环节生成（tkinter 没有翻转能力）

## 桌面侧边挂件

```bash
python quota_widget.py
```

无边框小挂件，默认停在屏幕右侧、置顶显示（UI v2，参考 dsh-usage / AgentLimits / VibePulse 的设计语言）：

- **深色卡片主题**（右键菜单可切浅色，选择持久化在 ui.json）
- 每行：头像 + 名称 + 小字注释 + **右侧大号余额数字** + **余额走势 sparkline**（记录在 history.json，走势下降显示橙色、上升蓝色）
- **状态色彩分级**：余额 < ¥10 橙色告警，< ¥2.5 红色告警
- 标题栏刷新按钮带**转圈动画**；点 ⚙ 打开配置窗口（跟随主题）；点行展开完整详情
- 默认 10 分钟自动刷新（右键可关）；右键菜单还有置顶开关、恢复任务栏显示、退出

## 命令行工具

```bash
python quota.py --init        # 生成 quotas.json 模板
python quota.py               # 查询
python quota.py --json        # 机器可读输出
```

- DeepSeek：`GET https://api.deepseek.com/user/balance`，显示总余额/赠送/充值
- 环境变量兜底：`DEEPSEEK_API_KEY`
- **custom 通道**：任何返回 JSON 的余额接口都能接，配置形如
  `{"name": "kimi", "url": "https://api.moonshot.cn/v1/users/me", "headers": {"Authorization": "Bearer {key}"}, "path": "data.balance"}`

## 曾经支持过的其他家（已按需求移除，接口笔记留此备查）

| 服务 | 接口 | 认证 |
| --- | --- | --- |
| OpenAI | `GET /v1/dashboard/billing/subscription` + `/usage`（官方在收缩） | API key |
| Kimi | `GET https://api.moonshot.cn/v1/users/me` | API key |
| 硅基流动 | `GET https://api.siliconflow.cn/v1/user/info` | API key |
| OpenRouter | `GET https://openrouter.ai/api/v1/auth/key` | API key |
| TokenHub（CodeBuddy Code CLI 套餐） | 腾讯云 API `DescribeTokenPlanList`，版本 2026-03-22，TC3-HMAC-SHA256 签名 | SecretId/SecretKey |
| 阿里云百炼（账号余额） | BssOpenApi `QueryAccountBalance`，版本 2017-12-14，RPC HMAC-SHA1 签名 | AccessKey |
| 火山方舟（Coding Plan 用量） | Ark `GetCodingPlanUsage`/`GetAFPUsage`，版本 2024-01-01，V4 HMAC-SHA256 签名 | AccessKey |

以上签名链路当时均用假密钥打真实端点验证过格式正确（返回认证类错误而非签名错误）。需要恢复任何一家：sk- 类的用 custom 通道即可零代码接入；云厂商签名类的参考本表参数重写约 30 行。

## 现成开源项目（2026-09 调研）

- **[cockpit-tools](https://github.com/jlcodes99/cockpit-tools)**（⭐18k，桌面应用）：Codex / Copilot / Cursor / Windsurf / Gemini CLI / **CodeBuddy** 的配额监控与多账号管理。CodeBuddy IDE 额度只能靠它。
- **[zcode-quota](https://github.com/2877905731/zcode-quota)**（Windows）：ZCode 状态栏插件，输入框下方常驻余额/套餐窗口 + 生成速度，支持 `/quota`。会补丁 ZCode 界面，装前建议先看源码。
- **[ccusage](https://github.com/ccusage/ccusage)**（⭐18.6k）：`npx ccusage` 统计本地 token 消耗；`npx @ccusage/codex` 看 Codex CLI 限流窗口。
- **DeepSeek Harness 套餐**：[dsh-usage](https://github.com/heekei/dsh-usage) 等 DSH 插件，自动识别 Kimi/智谱/DeepSeek/火山方舟套餐余量。

## 目录结构

```
quota-checker/
├── quota.py                查询核心 + DPAPI 加密配置（CLI 入口）
├── quota_pet.py            鲸鱼娘桌宠（tkinter）
├── quota_widget.py         桌面侧边挂件（tkinter）
├── mascot.py               挂件用的自绘猫咪帧生成器
├── pngtool.py              纯标准库 PNG 解码/编码/翻转（素材预处理用）
├── pet_assets/
│   ├── {front,side_l,side_r,back}.png   鲸鱼娘立绘四态
│   ├── {side_l_1,side_r_1}.png           走路第二帧
│   ├── {blink_1,blink_2}.png             可选眨眼帧
│   ├── {sleep_1,sleep_2}.png             可选睡眠帧
│   ├── manifest.json                     可选素材映射
│   ├── keyboard.png                      键盘与键位点亮层
│   ├── {hand,hand_up}.png               手（落下/抬起）
├── tools/                   素材构建脚本
├── data/                    配置与运行数据
└── README.md
```

运行时不需要任何第三方库（纯标准库，Windows 10/11）。
