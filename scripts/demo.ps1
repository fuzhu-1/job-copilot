# Job Copilot 一键 Demo：构建前端 + 启动后端 + 打开浏览器
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "已生成 .env，请先填入 LLM_API_KEY 后重新运行本脚本"
  exit 1
}

Write-Host "==> 构建前端"
Push-Location "app/web"
npm install
npm run build
Pop-Location

Write-Host "==> 启动后端 http://localhost:8000"
Start-Process -FilePath "uvicorn" -ArgumentList "app.main:app --port 8000" -WorkingDirectory $root -WindowStyle Hidden
Start-Sleep -Seconds 3
Start-Process "http://localhost:8000"
