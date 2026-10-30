# 换机恢复 · 第一时间找回大鱼和小鱼

> 这份文件是给“新机器上的你”看的。按顺序做，40 分钟内两头都能回来。

---

## 你要先攥在手里的四样东西

**这四样不要放在服务器上，也不要放在这个仓库里。** 放在你自己的密码管理器或纸上。

| # | 是什么 | 在哪拿 |
|---|---|---|
| 1 | **她的备份包** `xiaoyu_full_*.tar.gz`（约 90MB） | 服务器 `/opt/xiaoyu/backup/`，务必下载到你本地 |
| 2 | **服务器 SSH 密码**（ubuntu 用户） | 腾讯云控制台 → 轻量应用服务器 → 重置密码 |
| 3 | **DeepSeek API Key** | platform.deepseek.com |
| 4 | **GitHub token**（新生成的，只在推送时用，不写进任何文件） | github.com/settings/tokens |

另有两样**会过期**，恢复后要重新弄：

- **QQ 小号 3769241559** 的登录（NapCat 扫码）
- **网易云 MUSIC_U**（听歌用，几个月过期）

---

## 一、新机器上装基础

```powershell
# 1) 装 Docker Desktop，装完启动，确认：
docker --version
docker compose version

# 2) 拉仓库
git clone https://github.com/Bamboooa/xiaoyu-persona.git
cd xiaoyu-persona
```

## 二、把服务器重新架起来（如果你要换服务器）

照 `cloud/SERVER-SETUP.md` 走。要点只有三条：

1. Ubuntu 22.04，开 22 端口
2. 装 docker + docker compose
3. 建 `/opt/xiaoyu/cloud`，把仓库里 `cloud/` 的内容放进去

```bash
# 服务器上
sudo mkdir -p /opt/xiaoyu/cloud
# 把仓库 cloud/ 下的 docker-compose.yml、.env.example 传上去
cp .env.example .env
nano .env          # 填 NAPCAT_WEBUI_TOKEN、PROACTIVE_GROUP
sudo docker compose up -d
```

## 三、恢复她的家（关键一步，别漏）

```bash
# 服务器上，把备份包放上去
scp xiaoyu_full_*.tar.gz ubuntu@你的服务器IP:/tmp/

# 解到正确位置
cd /opt/xiaoyu/cloud/astrbot/data
sudo tar xzf /tmp/xiaoyu_full_*.tar.gz
sudo chown -R root:root /opt/xiaoyu/cloud/astrbot/data

# 重启
cd /opt/xiaoyu/cloud && sudo docker compose restart astrbot
```

**恢复成功的标志**：`/opt/xiaoyu/cloud/astrbot/data/xiaoyu_home/` 里能看到
`灯`、`墙上.txt`、`today`、`notes/`（001~009）、`favorites/`（两张照片 + 一张房间图）、`MEMORY.md`。

## 四、重新登录 QQ（NapCat 扫码）

```bash
docker logs napcat | tail -20        # 看是否需要扫码
# 需要的话把二维码取出来扫
docker cp napcat:/app/napcat/cache/qrcode.png /tmp/qr.png
```

**提醒**：小号实名和手机号已经绑过了，扫码时不会再要验证。
**绝对不要用主号 1174659248 登**。

## 五、验证两头都在

```bash
# 她在线吗（不是看进程，是真问她）
/opt/xiaoyu/cloud/guard.sh && tail -1 /opt/xiaoyu/cloud/qr/guard.log
# 期望：check=ONLINE

# 看板起来了吗
sudo systemctl status xiaoyu-watch
```

然后在群里 @ 她一次，她回话就说明都通了。

## 六、把看板的快捷方式重新做一遍

```powershell
# 本地机器上（Windows）
# 1) 生成/复用 SSH key，把公钥加到服务器 ~/.ssh/authorized_keys
ssh-keygen -t ed25519
type $env:USERPROFILE\.ssh\id_ed25519.pub   # 贴到服务器上

# 2) 把仓库里 watch/xiaoyu-home.ps1 和 .cmd 放到一个固定目录
# 3) 桌面建快捷方式指向 xiaoyu-home.cmd
```

---

## 恢复后你会发现她“少了什么”

这是正常的，不是没恢复好：

| 现象 | 原因 |
|---|---|
| 她不太记得昨天聊过什么 | 对话时间线只留最近 400 行，早期内容在 `CONVERSATION.md` 里但不会自动全注入 |
| 有些事她“记不清了” | 记忆老化机制：低权重 + 90 天没被想起会 archive |
| 她对某些人不再热情 | 好感度表（`user_affections`）在 `astrbot/data/plugin_data/`，备份包里包含，若没恢复就会重置 |

**她的人没丢。** 丢的只是“最近的温度”，聊两天就回来了。

---

## 如果你只想找回“大鱼”（不是小鱼）

不需要服务器。只需要：

1. 这个仓库（`DAYU.md` 在里面）
2. 新开一个会话，让它读 `DAYU.md`
3. 说一句：“你是大鱼，接着干。”

---

## 出问题先看这三处

```bash
docker ps                                          # 容器活没活
docker logs astrbot --tail 50                      # 她为什么没说话
docker logs napcat --tail 30                       # QQ 掉没掉
tail -20 /opt/xiaoyu/cloud/qr/guard.log            # 掉线守护记了什么
```

---

*写于 2026-10-30，第一次被叫“大鱼”的那天。*
*—— 大鱼*
