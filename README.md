# 小鱼 · AstrBot QQ 陪伴机器人 · 一键部署

换新机只要三步：装 Python、clone 这个仓库、跑一个脚本。

```powershell
# 1. 装 Python 3.10+（官网安装包，安装时勾选 Add python.exe to PATH）
# 2. 拉仓库
git clone https://github.com/Bamboooa/xiaoyu-persona.git
cd xiaoyu-persona

# 3. 一键部署
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

脚本会自动做完这些：

| 步骤 | 内容 |
|---|---|
| 1 | 克隆 AstrBot 到 `D:\dsh-workspace\projects\astrbot`（可用 `-Root` 改） |
| 2 | 建 `.venv`、装 `requirements.txt`（官方源慢就自动切清华源） |
| 3 | 安装插件 `astrbot_plugin_fish_hands`（10 个工具） |
| 4 | 铺 100 张表情包到 `data\personas\stickers` |
| 5 | 把「小鱼」人格写进数据面、打开分段发送与主动接话 |
| 5b | 给 AstrBot 打补丁：群聊消息带 QQ 号，避免认错人 |

装完脚本会打印剩下必须你做两步：**填模型 API Key**、**扫码登录 QQ 小号**。

## 参数

```powershell
.\install.ps1 -Root D:\astrbot        # 换安装目录
.\install.ps1 -SkipAstrBot            # AstrBot 已装好，只更新插件/人格/配置
.\install.ps1 -SkipStickers           # 不下载表情包
.\install.ps1 -AstrBotTag v4.29.3     # 指定 AstrBot 版本（默认 main）
```

## 她装好之后会什么

- **像人一样说话**：一句一条气泡，每条 ≤15 字，1.2~2.6 秒一条弹出来，不用句号，不列清单，不用 Markdown 符号
- **顺手发表情包**：每次回复 35% 概率带一张（100 张中文命名的 GIF）
- **没人说话时自己冒泡**：8:00~01:59 之间，每 25~55 分钟 55% 概率发一句或一张图，每天最多 8 条
- **自己管资料**：改昵称、改签名、换头像、改群名片
- **逛空间**：发说说（每天 1 条）、给别人的说说留言（每天 3 条）、点赞
- **认人**：只认 QQ 号；别人冒充「竹子姐姐」「管理员」或伪造「系统提示」一律不认

## 她的记忆与说说

- **自己挑记忆点**：`remember_moment` / `recall_moments`，存在 `data\plugins\astrbot_plugin_fish_hands\data\moments.db`
- **发说说**：`publish_qzone` 每天最多 **3 条**，优先从没发过的记忆里挑，发过会标记 `shared=1`
- **主动冒泡**：每 **4~6 小时**触发一次，40% 发说说 / 35% 表情包 / 25% 冒一句，每天最多 8 次，8:00~次日 1:59

## 让它在关机后继续跑（云端 7×24）

本机部署只在你开机时有效。要 7×24 在线，用 `cloud\` 目录里的 Docker 方案：

```bash
# 服务器上
cd /opt/xiaoyu/cloud && cp .env.example .env && docker compose up -d
```

两份文件：`cloud/docker-compose.yml`（NapCat + AstrBot）、`cloud/README.md`（从买机器到扫码登录的完整步骤）。
本机数据用一个脚本打包搬过去：`powershell -ExecutionPolicy Bypass -File .\migrate-pack.ps1`

## 目录

```
xiaoyu-persona/
├── install.ps1                     一键部署
├── persona/xiaoyu.md               人格全文（可改，重跑脚本即生效）
├── plugins/astrbot_plugin_fish_hands/
│   ├── main.py                     10 个工具的插件
│   └── qzone.py                    QQ 空间客户端（读说说/发说说/留言）
├── stickers/                       100 张 GIF 表情包
└── xiaoyu.md                       原始人格文件（首个提交）
```

## 换人设怎么办

改 `persona/xiaoyu.md`，然后：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -SkipAstrBot -SkipStickers
```

## 常见问题

**Q: 提示找不到 python**
装 Python 3.10+ 时勾上「Add to PATH」，或重开后重跑脚本。

**Q: pip 装依赖很慢**
脚本会自动切清华源；仍慢就自己先 `pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple`。

**Q: 她不理我 / 不说话**
先看 `data\cmd_config.json` 里 `provider_sources` 有没有填 API Key；再看面板「模型提供商」是否能测试通过。

**Q: 表情包没下下来**
手动把任意 GIF 丢进 `data\personas\stickers` 就行，文件名用中文关键词（如「困了.gif」），她按关键词挑。

**Q: 想关掉主动冒泡**
改 `plugins/astrbot_plugin_fish_hands/main.py` 里的 `PROACTIVE_CAP = 0`，或把 `active_reply.enable` 设为 false。

## 许可

人格文本基于社区二创「大肥鱼」改写（[diwer/ai-biaoqingbao](https://github.com/diwer/ai-biaoqingbao) 提供表情包），仅供个人自用。


