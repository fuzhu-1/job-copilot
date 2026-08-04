# Docker 一键启动
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
docker compose up --build -d
Write-Host "启动完成：http://localhost:8000"
