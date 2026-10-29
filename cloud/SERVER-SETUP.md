# 云服务器买与配（小鱼专用）

目标：一台 7×24 开机的 Linux 机器，跑 `napcat + astrbot` 两个容器。

## 一、买什么

| 项目 | 选什么 | 说明 |
|---|---|---|
| 厂商 | 腾讯云 / 阿里云 轻量应用服务器 | 都行，哪家有活动选哪家 |
| 地域 | **离你近的国内节点**（如上海/广州/北京） | 到 QQ 服务器延迟低，扫码登录更顺 |
| 配置 | **2 核 2G** 起（4G 更稳） | AstrBot 依赖含 faiss/pandas，1G 会 OOM |
| 系统镜像 | **Ubuntu 22.04 LTS** | 命令最简单，Docker 官方支持最好 |
| 带宽 | 3~5 Mbps 足够 | 只跑文字和图片 |
| 硬盘 | 40~60 GB | 系统 + 容器 + 日志 |
| 价格 | 新用户/学生机 ¥10~30/月 | 别买按量计费，买包月 |

> 不要买「虚拟主机/云虚机」，要能 SSH 登录的**云服务器**。

## 二、买完先做三件事

1. **重置密码 / 绑定密钥**（控制台 → 服务器 → 登录设置）
2. **放行端口**：轻量服务器在「防火墙」里加：
   - `22`（SSH）
   - `6185`（AstrBot 面板）
   - `6099`（NapCat 面板）
   - 建议：6185/6099 的来源 IP 只填你自己的公网 IP，别对 `0.0.0.0/0` 开放
3. **记下公网 IP**，例如 `1.2.3.4`

## 三、服务器上的命令（复制粘贴，一条条来）

```bash
# 1. 登录（Windows 用 PowerShell 或 Xshell/MobaXterm 都行）
ssh root@1.2.3.4

# 2. 装 Docker（官方脚本，含 compose 插件）
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker compose version        # 应输出 v2.x

# 3. 拉代码
apt update && apt install -y git unzip
git clone https://github.com/Bamboooa/xiaoyu-persona.git /opt/xiaoyu
cd /opt/xiaoyu/cloud

# 4. 配 .env（把 token 改成随机串；群号改成你的群）
cp .env.example .env
nano .env
#   NAPCAT_WEBUI_TOKEN=<随机串>
#   PROACTIVE_GROUP=624707019
#   Ctrl+O 回车保存，Ctrl+X 退出

# 5. 起容器
docker compose up -d
docker compose ps
docker compose logs -f astrbot      # Ctrl+C 退出日志
```

## 四、登录（只做一次）

1. 浏览器开 `http://1.2.3.4:6099` → 用 `.env` 里的 token 登录 NapCat
2. 扫二维码登录**小鱼的小号**（不是主号）
   - 异地首次登录，手机可能要求确认，正常点「允许」
3. 等 10 秒，`docker compose logs napcat | grep -i ws` 应看到反向 WebSocket 已连接 `ws://astrbot:6199/ws`
4. 开 `http://1.2.3.4:6185` → AstrBot 面板
   - 账号 `astrbot`，初始密码：`docker compose logs astrbot | grep -i password`
5. 面板 → 模型提供商 → 新增对话模型（DeepSeek），填 API Key
6. 面板 → 人格 → 确认「小鱼」在列表里并已设为默认

## 五、把本机数据搬过来

本机（PowerShell）：

```powershell
cd D:\dsh-workspace\projects\xiaoyu-deploy
powershell -ExecutionPolicy Bypass -File .\migrate-pack.ps1
scp .\xiaoyu-migrate.zip root@1.2.3.4:/opt/xiaoyu/
```

服务器：

```bash
cd /opt/xiaoyu/cloud/astrbot/data
unzip -o /opt/xiaoyu/xiaoyu-migrate.zip
docker compose restart astrbot
```

## 六、验证清单

- [ ] `docker compose ps` 两个容器都 `Up`
- [ ] `http://IP:6185` 能打开面板
- [ ] 群里 @ 小鱼 有回复
- [ ] `docker compose logs astrbot | grep 适配器已连接`
- [ ] `docker restart napcat` 后不用重新扫码（登录态已存卷里）

## 七、常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `docker compose up` 拉镜像很慢 | 国内拉 Docker Hub 慢 | 配镜像加速：`/etc/docker/daemon.json` 加 `{"registry-mirrors":["https://docker.m.daocloud.io"]}` 后 `systemctl restart docker` |
| AstrBot 容器反复重启 | 内存不足 | 升级到 2G/4G，或加 swap：`fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile` |
| NapCat 扫码后马上掉线 | 异地风控 | 手机端确认登录，或换常用网络环境扫码 |
| 面板打不开 | 防火墙没放行 | 控制台防火墙加 6185/6099 |
| 本机还能登同一个 QQ | 两边冲突 | 本机停掉 NapCat，一个号只能一处在线 |

## 八、日常维护

```bash
docker compose logs -f astrbot     # 看日志
docker compose restart astrbot     # 改完配置重启
docker compose pull && docker compose up -d   # 更新镜像
# 备份（每周）
tar czf ~/xiaoyu-backup-$(date +%F).tgz /opt/xiaoyu/cloud/astrbot/data /opt/xiaoyu/cloud/napcat
```
