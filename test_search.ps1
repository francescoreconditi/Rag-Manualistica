# Test ricerca RAG
$body = @{
    query = "Come impostare aliquota IVA?"
    top_k = 5
} | ConvertTo-Json

Write-Host "Invio richiesta di ricerca..." -ForegroundColor Cyan
$response = Invoke-RestMethod -Uri "http://localhost:8000/search" -Method Post -Body $body -ContentType "application/json"

Write-Host "`nRISPOSTA:" -ForegroundColor Green
$response | ConvertTo-Json -Depth 10 | Write-Host
