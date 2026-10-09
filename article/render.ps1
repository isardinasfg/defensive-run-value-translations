# Rebuild the defensive dives article.
#   .\render.ps1            reuse the cached query snapshots in data/
#   .\render.ps1 -Refresh   re-pull everything from BigQuery first
# Outputs: defensive_dives.html (single self-contained file) and
#          defensive_dives.md + defensive_dives_files/ (for the website later),
#          "Defensive Run Value Translations.pdf" (coach version, for Drive).
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
    # Coach PDF (for Drive): print a copy of the HTML with print.css injected.
    # The translator is interactive, so the PDF points to the web version.
    $edge = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
    $pdf = Join-Path $PSScriptRoot "Defensive Run Value Translations.pdf"
    $printCopy = Join-Path $env:TEMP "defensive_dives_print.html"
    $html = [IO.File]::ReadAllText((Join-Path $PSScriptRoot "defensive_dives.html"))
    $css = [IO.File]::ReadAllText((Join-Path $PSScriptRoot "print.css"))
    $html = $html.Replace("</head>", "<style>`n$css</style>`n</head>")
    $html = $html.Replace("the calculator below can also", "the interactive calculator in the web version of this article can also")
    [IO.File]::WriteAllText($printCopy, $html)
    Start-Process $edge -Wait -WindowStyle Hidden -ArgumentList @(
        "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=8000",
        "--print-to-pdf=`"$pdf`"", "file:///$($printCopy -replace '\\', '/')")
    Remove-Item $printCopy
    if (-not (Test-Path $pdf) -or (Get-Item $pdf).LastWriteTime -lt (Get-Item defensive_dives.html).LastWriteTime) {
        Write-Host "`nPDF build FAILED. The HTML and markdown were updated." -ForegroundColor Yellow
        exit 1
    }
    $built = (Get-Item defensive_dives.html).LastWriteTime
    Write-Host "`nDone: defensive_dives.html and the coach PDF updated at $built" -ForegroundColor Green
} finally {
    Pop-Location
}
