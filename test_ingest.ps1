# Test ingestione PDF
$body = @{
    urls = @("http://192.168.0.12:8000/t7adm_07501_711588.pdf")
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/ingest" -Method Post -Body $body -ContentType "application/json"
