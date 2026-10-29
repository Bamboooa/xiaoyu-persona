# 小鱼 · 云端 7×24 部署（Docker）

目标：**你的电脑关机，小鱼照样在群里说话、发说说。**

原理：换一台常开的机器（云服务器 / NAS / 旧笔记本）跑两个容器——

```
NapCat（QQ 登录，扫码）  --OneBot11 WS-->  AstrBot（人格 + 插件 + 记忆）
      :6099                                      :6185 面板 / :6199 反向WS
```

## 一、准备一台常开机器

| 方案 | 建议配置 | 成本 |
|---|---|---|
| 阿里云/腾讯云 轻量应用服务器 | 2 核 2G，Ubuntu 22.04 | ¥10~30/月（学生机更便宜） |
| 家里 NAS / 软路由 / 旧笔记本 | 2G 内存起 | 电费 |

> 内存低于 2G 会很卡（AstrBot 依赖里带 faiss、pandas）。
> 国内服务器访问 DeepSeek API 正常，不需要额外代理。

## 二、装 Docker

```bash
# Ubuntu / Debian
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
docker compose version      # 确认有 compose v2
```

## 三、把包传上去并启动

在**你自己的电脑**上，仓库根目录执行：

```bash
# 只传云端需要的东西
scp -r cloud root@<你的服务器IP>:/opt/xiaoyu
```

在**服务器**上：

```bash
cd /opt/xiaoyu/cloud
cp .env.example .env          # 改一下 token 和群号
docker compose up -d
docker compose logs -f astrbot
```

## 四、第一次登录（只做一次）

1. 浏览器打开 `http://<服务器IP>:6099` → 用 `.env` 里的 `NAPCAT_WEBUI_TOKEN` 登录 NapCat
2. 扫二维码登录 **小鱼的小号**（不是主号）
3. NapCat → 网络配置 → 确认「反向 WebSocket」指向 `ws://astrbot:6199/ws`（compose 已配好，通常自动连上）
4. 打开 `http://<服务器IP>:6185` → AstrBot 面板（账号 `astrbot`，初始密码看容器日志）
5. 面板 → 模型提供商 → 填 DeepSeek/其他 API Key
6. 面板 → 人格 → 确认「小鱼」已存在并在用

## 五、把本机数据迁过去

在**本机**执行 `migrate-pack.ps1`（仓库根目录），会生成 `xiaoyu-migrate.zip`，包含：

- `persona/xiaoyu.md`（人格）
- `plugins/astrbot_plugin_fish_hands/`（插件 + memory.py）
- `moments.db`（她记下的事）
- `cmd_config.snippet.json`（关键配置项，供手工对照）

传到服务器后解压进 `cloud/astrbot/data/` 对应位置：

```
cloud/astrbot/data/personas/xiaoyu.md
cloud/astrbot/data/personas/stickers/*.gif
cloud/astrbot/data/plugins/astrbot_plugin_fish_hands/
cloud/astrbot/data/plugins/astrbot_plugin_fish_hands/data/moments.db
```

然后 `docker compose restart astrbot`。

## 六、注意事项

1. **同一个 QQ 号只能在一个地方登录**：云端上线后，本机的小鱼会被踢下线。别两边同时跑。
2. **异地登录会触发验证**：第一次在云端扫码时，手机可能要求确认；之后登录态存在 `napcat/qq` 卷里，重启容器不用重扫。
3. **风控**：云端 IP 和家庭宽带 IP 不同，频繁切换登录地点更容易被腾讯盯上。选定云端后就不要来回切。
4. **端口安全**：6099 / 6185 建议只对你自己 IP 开放，或套 Nginx + 密码。`.env` 里的 `NAPCAT_WEBUI_TOKEN` 一定要改。
5. **备份**：`astrbot/data` 和 `napcat/qq` 两个目录定期打包，换机器直接搬。

## 七、和本机部署的关系

- 本机那套（`install.ps1`）不用删，留着做调试/备份；只要**别同时登录同一个 QQ**。
- 人格、插件、记忆都是文件，随时可以两边互相同步。
