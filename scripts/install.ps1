# 開發用：把本 repo 的 ai-usage-log/ 以目錄連接 (Junction) 連到使用者層級的 skills 目錄。
# 不需要系統管理員權限。改程式後不必重新複製，到課程專案開新的 Claude Code 對話即可測試。
# 用法：powershell -ExecutionPolicy Bypass -File scripts\install.ps1 [-Uninstall]
param([switch]$Uninstall)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repoRoot "ai-usage-log"
$skillsDir = Join-Path $env:USERPROFILE ".claude\skills"
$link = Join-Path $skillsDir "ai-usage-log"

if (-not (Test-Path (Join-Path $source "SKILL.md"))) { throw "找不到 $source\SKILL.md" }

if (Test-Path $link) {
    $item = Get-Item $link -Force
    if ($item.LinkType -ne "Junction") {
        throw "$link 已存在且不是連接（可能是複製安裝的版本），請自行確認後移除再重試。"
    }
    # 只移除連接本身，不會刪到 repo 內的檔案
    [System.IO.Directory]::Delete($link, $false)
    Write-Host "已移除既有連接 $link"
}
if ($Uninstall) { return }

New-Item -ItemType Directory -Force -Path $skillsDir | Out-Null
New-Item -ItemType Junction -Path $link -Target $source | Out-Null
Write-Host "已建立連接：$link -> $source"
