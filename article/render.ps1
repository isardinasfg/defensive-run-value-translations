# Rebuild the defensive dives article.
#   .\render.ps1            reuse the cached query snapshots in data/
#   .\render.ps1 -Refresh   re-pull everything from BigQuery first
# Outputs: defensive_dives.html (single self-contained file) and
#          defensive_dives.md + defensive_dives_files/ (for the website later).
param([switch]$Refresh)

$env:QUARTO_PYTHON = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
Push-Location $PSScriptRoot
try {
    # HTML first: its embed-resources step deletes defensive_dives_files/,
    # which the markdown build then recreates with its figures.
    if ($Refresh) {
        quarto render defensive_dives.qmd --to html -P refresh:true
    } else {
        quarto render defensive_dives.qmd --to html
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nHTML build FAILED (see the error above). defensive_dives.html was not updated." -ForegroundColor Red
        exit 1
    }
    quarto render defensive_dives.qmd --to gfm
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nMarkdown build FAILED (see the error above). The HTML was updated." -ForegroundColor Yellow
        exit 1
    }
    $built = (Get-Item defensive_dives.html).LastWriteTime
    Write-Host "`nDone: defensive_dives.html updated at $built" -ForegroundColor Green
} finally {
    Pop-Location
}
