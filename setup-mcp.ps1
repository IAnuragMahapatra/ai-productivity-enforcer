#!/usr/bin/env pwsh
# PowerShell script to initialize uv project and install all mcp_*.py files inside src to Claude MCP

Write-Host "Initializing uv project..." -ForegroundColor Green
uv init
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Attempting to sync uv project..."
    uv sync
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed. Please ensure uv is installed. See: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    } else {
        Write-Host "Project synced successfully." -ForegroundColor Green
    }
}

Write-Host "Adding MCP CLI dependency..." -ForegroundColor Green
uv add mcp[cli]
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to add MCP CLI dependency"
    exit 1
}

Write-Host "Removing automatically generated files..." -ForegroundColor Green

# Remove main.py
if (Test-Path "main.py") {
    Remove-Item "main.py" -Force
    Write-Host "Deleted main.py" -ForegroundColor Yellow
} else {
    Write-Host "No main.py file found to delete" -ForegroundColor Yellow
}

# Remove README.md
if (Test-Path "README.md") {
    Remove-Item "README.md" -Force
    Write-Host "Deleted README.md" -ForegroundColor Yellow
} else {
    Write-Host "No README.md file found to delete" -ForegroundColor Yellow
}

Write-Host "Searching for server files inside src..." -ForegroundColor Green

$serverFiles = Get-ChildItem -Path "src" -Filter "mcp_*.py" -File

if ($serverFiles.Count -eq 0) {
    Write-Warning "No server files found inside src"
    exit 0
}

Write-Host "Found $($serverFiles.Count) server file(s):" -ForegroundColor Yellow
foreach ($file in $serverFiles) {
    Write-Host "  - $($file.FullName)" -ForegroundColor Cyan
}

Write-Host "Installing files to Claude Desktop..." -ForegroundColor Green

$installedCount = 0
foreach ($file in $serverFiles) {
    Write-Host "Installing $($file.FullName)..." -ForegroundColor Yellow
    $relativePath = "src\$($file.Name)"
    uv run mcp install $relativePath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install $($file.Name)"
    } else {
        Write-Host "Successfully installed $($file.Name)" -ForegroundColor Green
        $installedCount++
    }
}

if ($installedCount -eq 0) {
    Write-Warning "Please ensure Claude Desktop is installed. See: https://claude.ai/download"
    exit 1
}

Write-Host "All server files installed to Claude Desktop successfully!" -ForegroundColor Green