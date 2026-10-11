# 本地一键启动：API + 两个消费者 + 前端（各开一个 PowerShell 窗口）
# 用法：.\start_all.ps1
$root = $PSScriptRoot
$py = Join-Path $root "venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

function Start-Window($title, $command, $dir) {
    Start-Process powershell -WorkingDirectory $dir -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle='$title'; $command"
}

Start-Window "API :8000"          "& '$py' -m uvicorn main:app --port 8000 --reload" $root
Start-Window "stock-consumer"     "& '$py' -m app.consumer.stock_consumer"          $root
Start-Window "dlq-consumer"       "& '$py' -m app.consumer.dlq_consumer"            $root
Start-Window "frontend :5173"     "npm run dev"                                     (Join-Path $root "frontend")

Write-Host "已启动：前端 http://localhost:5173  接口文档 http://127.0.0.1:8000/docs"
