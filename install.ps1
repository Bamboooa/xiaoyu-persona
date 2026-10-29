<#
小鱼（xiaoyu）一键部署脚本 · AstrBot QQ 陪伴机器人

用法（新机子上，PowerShell 里跑）：
    git clone https://github.com/Bamboooa/xiaoyu-persona.git
    cd xiaoyu-persona
    powershell -ExecutionPolicy Bypass -File .\install.ps1

可选参数：
    -Root D:\astrbot        安装目录（默认 D:\dsh-workspace\projects\astrbot）
    -SkipAstrBot            只装插件/人格，不重装 AstrBot 本体（已装过时用）
    -SkipStickers           不下载表情包
    -AstrBotTag v4.29.3     指定 AstrBot 版本（默认 main 分支）

做完之后脚本会告诉你还差哪两步（填模型 key、扫码登录 QQ）。
#>

[CmdletBinding()]
param(
    [string]$Root = "D:\dsh-workspace\projects\astrbot",
    [string]$AstrBotTag = "main",
    [switch]$SkipAstrBot,
    [switch]$SkipStickers
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Step($n, $msg) { Write-Host "`n[$n] $msg" -ForegroundColor Cyan }
function Ok($msg)        { Write-Host "    OK  $msg" -ForegroundColor Green }
function Warn($msg)      { Write-Host "    !!  $msg" -ForegroundColor Yellow }

# ---------- 0. 前置检查 ----------
Step 0 "检查环境"
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { throw "没找到 python。先装 Python 3.10+（勾选 Add to PATH）再跑本脚本。" }
$pyVer = & python -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$pyVer -lt [version]"3.10") { throw "Python 版本太低：$pyVer，需要 3.10+。" }
Ok "python $pyVer"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Warn "没找到 git，将改用 zip 下载 AstrBot"
    $useGit = $false
} else { $useGit = $true; Ok "git 可用" }

# ---------- 1. AstrBot 本体 ----------
if (-not $SkipAstrBot) {
    Step 1 "准备 AstrBot -> $Root"
    if (Test-Path (Join-Path $Root "main.py")) {
        Ok "已存在，跳过克隆"
    } elseif ($useGit) {
        New-Item -ItemType Directory -Force -Path (Split-Path $Root) | Out-Null
        git -c http.proxy= -c https.proxy= clone --depth 1 --branch $AstrBotTag https://github.com/AstrBotDevs/AstrBot.git $Root 2>&1 | Out-Null
        if (-not (Test-Path (Join-Path $Root "main.py"))) { throw "AstrBot 克隆失败，检查网络后重试。" }
        Ok "已克隆 $AstrBotTag"
    } else {
        $zip = Join-Path $env:TEMP "AstrBot.zip"
        Invoke-WebRequest -Uri "https://codeload.github.com/AstrBotDevs/AstrBot/zip/refs/heads/main" -OutFile $zip
        Expand-Archive -Path $zip -DestinationPath (Split-Path $Root) -Force
        $inner = Get-ChildItem (Split-Path $Root) -Directory | Where-Object { $_.Name -like "AstrBot-*" } | Select-Object -First 1
        if ($inner) { Move-Item $inner.FullName $Root -Force }
        Ok "已解压"
    }

    Step 2 "建虚拟环境并装依赖（约 3~8 分钟）"
    $venvPy = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPy)) { & python -m venv (Join-Path $Root ".venv") }
    & $venvPy -m pip install -q -U pip
    Push-Location $Root
    try {
        & $venvPy -m pip install -q -r requirements.txt --timeout 120 --retries 3
        if ($LASTEXITCODE -ne 0) {
            Warn "官方源太慢，改用清华源重试"
            & $venvPy -m pip install -q -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 120
        }
    } finally { Pop-Location }
    Ok "依赖装好"
}

# ---------- 3. 插件 ----------
Step 3 "安装 fish_hands 插件"
$pluginDst = Join-Path $Root "data\plugins\astrbot_plugin_fish_hands"
New-Item -ItemType Directory -Force -Path $pluginDst | Out-Null
Copy-Item (Join-Path $here "plugins\astrbot_plugin_fish_hands\*") $pluginDst -Recurse -Force
Remove-Item (Join-Path $pluginDst "data") -Recurse -Force -ErrorAction SilentlyContinue
Ok "插件 -> $pluginDst"

# ---------- 4. 表情包 ----------
if (-not $SkipStickers) {
    Step 4 "下载表情包（100 张 GIF）"
    $stickerDst = Join-Path $Root "data\personas\stickers"
    New-Item -ItemType Directory -Force -Path $stickerDst | Out-Null
    $count = (Get-ChildItem $stickerDst -Filter *.gif -ErrorAction SilentlyContinue | Measure-Object).Count
    if ($count -ge 50) {
        Ok "已有 $count 张，跳过"
    } elseif (Test-Path (Join-Path $here "stickers")) {
        Copy-Item (Join-Path $here "stickers\*.gif") $stickerDst -Force
        Ok "从仓库自带复制"
    } else {
        Warn "仓库里没带表情包，改为在线拉取"
        $z = Join-Path $env:TEMP "bqb.zip"
        try {
            Invoke-WebRequest -Uri "https://codeload.github.com/diwer/ai-biaoqingbao/zip/refs/heads/main" -OutFile $z
            Expand-Archive $z -DestinationPath $env:TEMP -Force
            $pack = Get-ChildItem $env:TEMP -Directory | Where-Object { $_.Name -like "ai-biaoqingbao-*" } | Select-Object -First 1
            $catPath = Join-Path $pack.FullName "docs\catalog.json"
            $cat = Get-Content $catPath -Raw -Encoding UTF8 | ConvertFrom-Json
            foreach ($it in $cat) {
                $src = Join-Path $pack.FullName ("stickers\512\" + $it.id + ".gif")
                if (-not (Test-Path $src)) { $src = Join-Path $pack.FullName ("docs\" + $it.id + ".gif") }
                if (Test-Path $src) {
                    $label = ($it.label -replace '[\\/:*?"<>|\s]+', '')
                    Copy-Item $src (Join-Path $stickerDst ($label + ".gif")) -Force
                }
            }
            Ok ("已拉取 " + (Get-ChildItem $stickerDst -Filter *.gif | Measure-Object).Count + " 张")
        } catch {
            Warn "表情包没下成，不影响使用；稍后可手动放进 $stickerDst"
        }
    }
}

# ---------- 5. 人格 + 配置 ----------
Step 5 "写入人格与关键配置"
$personaSrc = Join-Path $here "persona\xiaoyu.md"
if (-not (Test-Path $personaSrc)) { $personaSrc = Join-Path $here "xiaoyu.md" }
$cfgPath = Join-Path $Root "data\cmd_config.json"
$pyPatch = @'
import json, sqlite3, sys, os, datetime, pathlib

root, persona_path = sys.argv[1], sys.argv[2]
prompt = pathlib.Path(persona_path).read_text(encoding="utf-8").strip()
cfg_path = pathlib.Path(root) / "data" / "cmd_config.json"

# 1) 人格进库（首次出现 data_v4.db 需要先启动过一次；没有库就先落文件，启动后由下一次运行补写）
db_path = pathlib.Path(root) / "data" / "data_v4.db"
if db_path.exists():
    con = sqlite3.connect(str(db_path))
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    row = con.execute("select id from personas where persona_id='xiaoyu'").fetchone()
    if row:
        con.execute("update personas set system_prompt=?, updated_at=? where persona_id='xiaoyu'", (prompt, now))
    else:
        nid = con.execute("select coalesce(max(id),0)+1 from personas").fetchone()[0]
        con.execute(
            "insert into personas (created_at, updated_at, id, persona_id, system_prompt,"
            " begin_dialogs, tools, skills, custom_error_message, folder_id, sort_order)"
            " values (?,?,?,?,?,'[]','null','null',NULL,NULL,0)",
            (now, now, nid, "xiaoyu", prompt))
    con.commit()
    con.close()
    print("persona: installed into db")
else:
    print("persona: db not found, will apply on next run")

# 2) 配置项
if cfg_path.exists():
    cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    ps = cfg.setdefault("provider_settings", {})
    ps["persona_pool"] = ["xiaoyu"]
    ps["default_persona_id"] = "xiaoyu"
    ltm = cfg.setdefault("provider_ltm_settings", {})
    ltm["active_reply"] = {"enable": True, "method": "possibility_reply",
                           "possibility_reply": 0.6, "whitelist": []}
    sr = cfg.setdefault("platform_settings", {}).setdefault("segmented_reply", {})
    sr.update({"enable": True, "only_llm_result": True, "interval_method": "random",
               "interval": "1.2,2.6", "split_mode": "words", "split_words": ["\n"],
               "content_cleanup_rule": "[*#`]+|＊+"})
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print("config: patched")
else:
    print("config: not found (先启动一次 AstrBot 再跑本脚本)")
'@
$patchFile = Join-Path $env:TEMP "xiaoyu_patch.py"
[System.IO.File]::WriteAllText($patchFile, $pyPatch, $utf8)
& python $patchFile $Root $personaSrc

# ---------- 6. 收尾 ----------
Step 6 "完成"
Write-Host @"

下一步（必须做，否则她不会说话）：

  1. 启动 AstrBot：
       cd "$Root"
       .\.venv\Scripts\python.exe main.py
     浏览器打开 http://127.0.0.1:6185  账号 astrbot，密码在 data\cmd_config.json 的 dashboard.password（首次启动控制台会打印初始密码）

  2. 面板 -> 模型提供商 -> 新增一个对话模型（DeepSeek/OpenAI/硅基流动都行），填 API Key

  3. 接 QQ（二选一）：
     a) 面板里加平台 aiocqhttp（端口 6199），再用 NapCat 扫码登录一个小号
     b) 只用面板的「聊天」功能测试，不接 QQ

  人格已装好，名字叫「小鱼」；表情包在 data\personas\stickers。
  她的能力：改昵称/签名/头像/群名片、发空间说说、给别人空间留言、点赞、发表情包、没人的时候自己冒泡。
"@ -ForegroundColor Gray
