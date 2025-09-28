# E-Modal Container API Test Script (PowerShell)
# =============================================

Write-Host "🧪 E-Modal Container API Test" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Green

# Check if API is running
Write-Host "🔍 Checking API status..." -ForegroundColor Yellow

try {
    $healthResponse = Invoke-WebRequest -Uri "http://localhost:5000/health" -Method GET -TimeoutSec 5
    $healthData = $healthResponse.Content | ConvertFrom-Json
    
    Write-Host "✅ API Status: $($healthData.status)" -ForegroundColor Green
    Write-Host "📊 Active Sessions: $($healthData.active_sessions)" -ForegroundColor Green
    Write-Host "🔗 Service: $($healthData.service)" -ForegroundColor Green
    
    # Test container extraction
    Write-Host "`n📦 Testing Container Extraction..." -ForegroundColor Yellow
    Write-Host "⚠️  This will:" -ForegroundColor Yellow
    Write-Host "  - Use 2captcha balance" -ForegroundColor Yellow
    Write-Host "  - Take 1-2 minutes" -ForegroundColor Yellow
    Write-Host "  - Download Excel file" -ForegroundColor Yellow
    
    $continue = Read-Host "`n💰 Continue? (y/N)"
    
    if ($continue -eq "y" -or $continue -eq "Y") {
        
        # Prepare request body
        $requestBody = @{
            username = "jfernandez"
            password = "taffie"
            captcha_api_key = "5a0a4a97f8b4c9505d0b719cd92a9dcb"
            keep_browser_alive = $false
        } | ConvertTo-Json
        
        Write-Host "`n🚀 Starting container extraction..." -ForegroundColor Green
        Write-Host "⏳ Please wait..." -ForegroundColor Yellow
        
        $startTime = Get-Date
        
        try {
            # Make the request with longer timeout
            $response = Invoke-WebRequest `
                -Uri "http://localhost:5000/get_containers" `
                -Method POST `
                -Body $requestBody `
                -ContentType "application/json" `
                -TimeoutSec 300 `
                -OutFile "containers_$(Get-Date -Format 'yyyyMMdd_HHmmss').xlsx"
            
            $duration = (Get-Date) - $startTime
            
            if ($response.StatusCode -eq 200) {
                $fileName = "containers_$(Get-Date -Format 'yyyyMMdd_HHmmss').xlsx"
                $fileSize = (Get-Item $fileName).Length
                
                Write-Host "`n🎉 SUCCESS! Container data extracted!" -ForegroundColor Green
                Write-Host "=================================" -ForegroundColor Green
                Write-Host "📄 File: $fileName" -ForegroundColor Green
                Write-Host "📊 Size: $($fileSize) bytes" -ForegroundColor Green
                Write-Host "⏱️ Duration: $($duration.TotalSeconds.ToString('F1')) seconds" -ForegroundColor Green
                Write-Host "📍 Location: $((Get-Item $fileName).FullName)" -ForegroundColor Green
            } else {
                Write-Host "❌ Request failed with status: $($response.StatusCode)" -ForegroundColor Red
            }
            
        } catch {
            $duration = (Get-Date) - $startTime
            Write-Host "`n❌ EXTRACTION FAILED" -ForegroundColor Red
            Write-Host "📝 Error: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "⏱️ Duration: $($duration.TotalSeconds.ToString('F1')) seconds" -ForegroundColor Yellow
            
            if ($_.Exception.Message -like "*timeout*") {
                Write-Host "`n💡 SOLUTION:" -ForegroundColor Yellow
                Write-Host "  - Request timed out (>5 minutes)" -ForegroundColor Yellow
                Write-Host "  - This usually indicates browser issues" -ForegroundColor Yellow
                Write-Host "  - Check VPN connection and try again" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "⏭️ Skipping container extraction test" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "❌ API server not running" -ForegroundColor Red
    Write-Host "💡 Start it with: python emodal_business_api.py" -ForegroundColor Yellow
}

Write-Host "`n🎉 Test completed!" -ForegroundColor Green

