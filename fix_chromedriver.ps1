# ChromeDriver Fix Script for Windows Server
# =========================================

Write-Host "🔧 ChromeDriver Fix Script" -ForegroundColor Green
Write-Host "=========================" -ForegroundColor Green

# Clear corrupted cache
Write-Host "`n🧹 Clearing corrupted cache..." -ForegroundColor Yellow
$cacheDirs = @(
    "$env:USERPROFILE\.wdm",
    "$env:USERPROFILE\.cache\selenium"
)

foreach ($dir in $cacheDirs) {
    if (Test-Path $dir) {
        try {
            Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  ✅ Cleared: $dir" -ForegroundColor Green
        } catch {
            Write-Host "  ⚠️ Could not clear: $dir" -ForegroundColor Yellow
        }
    }
}

# Run Python fix script
Write-Host "`n📦 Running Python fix script..." -ForegroundColor Yellow
try {
    python fix_chromedriver.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✅ ChromeDriver fix completed successfully!" -ForegroundColor Green
    } else {
        Write-Host "`n❌ ChromeDriver fix failed!" -ForegroundColor Red
    }
} catch {
    Write-Host "`n❌ Error running fix script: $_" -ForegroundColor Red
}

Write-Host "`nPress any key to continue..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
