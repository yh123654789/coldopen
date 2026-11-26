# 一条命令跑完「片头卡 → 封面 → 上传 → 填标题简介」，最后两下留给人。
#
#   .\examples\publish_one.ps1 -Video "D:\ep.mp4" -Title "地海" -Pinyin dh
#
# 前置：已跑过 install.ps1 和 dy.py calibrate，抖音客户端已登录并停在上传页。

param(
  [Parameter(Mandatory = $true)][string]$Video,
  [string]$Title = "地海",
  [string]$Pinyin = "dh",
  [string]$PinyinPick = "1",
  [string]$En = "THE MYSTERIOUS SEA",
  [string]$Chapter = "",
  [string]$Desc = "AI 生成短剧，人物、场景与配音均由 AI 创作`n#地海 #AI创作 #AI短剧 #悬疑 #科幻",
  [string]$Out = "cover",
  [switch]$SkipCard,
  [switch]$SkipUpload
)

$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"
$dy = ".\scripts\dy.py"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

if (-not $SkipCard) {
  Step "生成电影片头卡并拼接成片"
  & $py .\scripts\make_title_card.py --video $Video --title $Title --en $En `
      --chapter $Chapter --out $Out
}

Step "把客户端窗口规整到标准尺寸"
& $py $dy front

if (-not $SkipUpload) {
  Step "打开发布页并上传（上传完成后按回车继续）"
  Write-Host "   如果不在发布页：点右上「投稿」→「发布作品」"
  Read-Host "   准备好后按回车，开始点上传按钮"
  & $py $dy click upload_video_button 2
  & $py $dy dialog "$PWD\$Out\master_with_title.mp4"
  Read-Host "   等进度跑完（约 20 秒），按回车继续"
}

Step "填简介（剪贴板直粘）"
& $py $dy click desc_field 1
& $py $dy paste $Desc
& $py $dy key escape

Step "填标题（输入法注入，先截图确认候选）"
& $py $dy click desc_field 1
& $py $dy hotkey shift tab
& $py $dy ime $Pinyin $PinyinPick
& $py $dy shot title_check
Write-Host "   看 out\shots\title_check.png 确认标题是否正确" -ForegroundColor Yellow

Step "剩下两下交给人"
Write-Host "   1) 点一张 AI 推荐封面 → 点「设置竖封面」"
Write-Host "   2) 确认「谁可以看 = 公开」→ 点「发布」"
