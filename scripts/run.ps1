# Job Copilot 一键启动脚本
# 用法: powershell -ExecutionPolicy Bypass -File scripts\run.ps1   （加 -NoBrowser 可不自动打开浏览器）
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$envFile = Join-Path $root ".env"
$python = Join-Path $root ".venv\Scripts\python.exe"
$port = 8000
$url = "http://127.0.0.1:$port"

if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $root ".env.example") $envFile
    Write-Host "[错误] 尚未配置 .env，已从示例生成。请先编辑 $envFile 填入 LLM_API_KEY，再重新运行本脚本。" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $python)) {
    Write-Host "[错误] 未找到虚拟环境 $python，请先执行 pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}

# 1) 从 .env 显式加载配置到当前进程环境（覆盖任何继承的环境变量，防止被外部覆盖）
$envFromFile = @{}
Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $idx = $line.IndexOf("=")
        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        $envFromFile[$key] = $value
        Set-Item -Path "Env:$key" -Value $value
    }
}

# 2) 校验 LLM 模型名：配置的模型必须存在于当前 Key 可用的模型列表中，否则自动修正
$base = $env:LLM_BASE_URL
if (-not $base) { $base = "https://api.openai.com/v1" }
$model = $env:LLM_MODEL
if (-not $model) { $model = "gpt-4o-mini" }
try {
    $models = (Invoke-RestMethod -Uri "$($base.TrimEnd('/'))/models" -Headers @{ Authorization = "Bearer $($env:LLM_API_KEY)" } -TimeoutSec 15).data.id
    if ($models -notcontains $model) {
        $fixed = if ($models -contains "deepseek-v4-flash") { "deepseek-v4-flash" } else { $models[0] }
        Write-Host "[提示] 配置的模型 $model 不在当前 Key 的可用模型列表($($models -join '/'))中，自动改用 $fixed" -ForegroundColor Yellow
        $model = $fixed
        Set-Item -Path "Env:LLM_MODEL" -Value $fixed
        $content = Get-Content $envFile
        $newContent = $content | ForEach-Object {
            if ($_ -match "^LLM_MODEL=") { "LLM_MODEL=$fixed" } else { $_ }
        }
        Set-Content -Path $envFile -Value $newContent -Encoding UTF8
    } else {
        Write-Host "LLM 模型检查通过：$model"
    }
} catch {
    Write-Host "[警告] 无法联网校验模型列表（$($_.Exception.Message)），沿用配置：$model" -ForegroundColor Yellow
}

# 3) 清理 8000 端口上的旧进程
$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $oldPid = $listener | Select-Object -First 1 -ExpandProperty OwningProcess
    Write-Host "正在停止旧服务进程 (pid $oldPid)..."
    Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# 4) 启动后端（隐藏窗口）
Write-Host "正在启动后端 $url ..."
$proc = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$port" -WorkingDirectory $root -WindowStyle Hidden -PassThru

# 5) 等待健康检查
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $res = Invoke-WebRequest -Uri "$url/health" -UseBasicParsing -TimeoutSec 3
        if ($res.StatusCode -eq 200) { $ok = $true; break }
    } catch {
        if ($proc.HasExited) { break }
    }
}

if ($ok) {
    Write-Host "启动成功：$url （进程 pid $($proc.Id)，日志见终端）" -ForegroundColor Green
    if (-not $NoBrowser) {
        Start-Process $url
    }
} else {
    Write-Host "[错误] 服务启动失败或健康检查超时" -ForegroundColor Red
    exit 1
}
