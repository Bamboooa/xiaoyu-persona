<#
把本机的小鱼数据打成一个包，方便传到云服务器。

用法：
    powershell -ExecutionPolicy Bypass -File .\migrate-pack.ps1
    powershell -ExecutionPolicy Bypass -File .\migrate-pack.ps1 -AstrBotRoot D:\dsh-workspace\projects\astrbot

产出：xiaoyu-migrate.zip（含人格、插件、记忆库、配置片段）
#>

[CmdletBinding()]
param(
    [string]$AstrBotRoot = "D:\dsh-workspace\projects\astrbot",
    [string]$Out = ".\xiaoyu-migrate.zip"
)

$ErrorActionPreference = "Stop"
$stage = Join-Path $env:TEMP ("xiaoyu_migrate_" + [guid]::NewGuid().ToString("N").Substring(0, 6))
New-Item -ItemType Directory -Force -Path $stage | Out-Null

function Copy-IfExists($src, $dstDir) {
    if (Test-Path $src) {
        New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
        Copy-Item $src $dstDir -Recurse -Force
        Write-Host "  + $src"
    } else {
        Write-Host "  - 跳过（不存在）: $src" -ForegroundColor Yellow
    }
}

Write-Host "[1/4] 人格"
Copy-IfExists (Join-Path $AstrBotRoot "data\personas\xiaoyu.md")      (Join-Path $stage "personas")
Copy-IfExists (Join-Path $AstrBotRoot "data\personas\stickers")       (Join-Path $stage "personas")

Write-Host "[2/4] 插件"
$plug = Join-Path $AstrBotRoot "data\plugins\astrbot_plugin_fish_hands"
Copy-IfExists $plug (Join-Path $stage "plugins")
Get-ChildItem (Join-Path $stage "plugins") -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "[3/4] 记忆库（随插件目录一起打包，无需单独拷贝）"
if (Test-Path (Join-Path $plug "data\moments.db")) {
    Write-Host "  + moments.db 已在 plugins\astrbot_plugin_fish_hands\data 内"
} else { Write-Host "  - 还没有记忆库，跳过" -ForegroundColor Yellow }
Write-Host "[4/4] 关键配置片段"
$cfgPath = Join-Path $AstrBotRoot "data\cmd_config.json"
if (Test-Path $cfgPath) {
    $cfg = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $snippet = [ordered]@{
        provider_settings = [ordered]@{
            persona_pool       = $cfg.provider_settings.persona_pool
            default_persona_id = $cfg.provider_settings.default_persona_id
        }
        provider_ltm_settings = $cfg.provider_ltm_settings
        platform_settings_segmented_reply = $cfg.platform_settings.segmented_reply
        platform = $cfg.platform
    }
    $snippet | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $stage "cmd_config.snippet.json") -Encoding UTF8
    Write-Host "  + cmd_config.snippet.json（API Key 不在里面，需要到云端重新填）"
}

if (Test-Path $Out) { Remove-Item $Out -Force }
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $Out -CompressionLevel Optimal
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue

$size = [math]::Round((Get-Item $Out).Length / 1MB, 1)
Write-Host ""
Write-Host "完成：$((Resolve-Path $Out).Path)  ($size MB)" -ForegroundColor Green
Write-Host @"
传到服务器：
  scp $Out root@<服务器IP>:/opt/xiaoyu/
服务器上解压到 AstrBot 数据目录：
  cd /opt/xiaoyu/cloud/astrbot/data
  unzip -o /opt/xiaoyu/$(Split-Path $Out -Leaf)
  docker compose restart astrbot
"@ -ForegroundColor Gray
