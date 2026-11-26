# douyin-publish 一键安装（Windows / PowerShell）
# 用法：右键“使用 PowerShell 运行”，或在终端里  powershell -ExecutionPolicy Bypass -File .\install.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "==> 检查 Python" -ForegroundColor Cyan
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { throw "没找到 Python。先装 Python 3.10+：https://www.python.org/downloads/" }
$ver = (& python -c "import sys;print('.'.join(map(str,sys.version_info[:2])))").Trim()
Write-Host "    Python $ver"
if ([version]$ver -lt [version]"3.10") { throw "需要 Python 3.10 或更新，当前 $ver" }

Write-Host "==> 创建虚拟环境 .venv" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) { & python -m venv .venv }

Write-Host "==> 安装依赖" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip -q
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "==> 环境自检" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" ".\scripts\dy.py" doctor

Write-Host ""
Write-Host "装好了。下一步：" -ForegroundColor Green
Write-Host "  1) 打开抖音客户端（登录好）"
Write-Host "  2) .\.venv\Scripts\python.exe .\scripts\dy.py front"
Write-Host "  3) .\.venv\Scripts\python.exe .\scripts\dy.py calibrate    # 一次性校准这台机器"
Write-Host "  4) 按 README 的流程发布"
