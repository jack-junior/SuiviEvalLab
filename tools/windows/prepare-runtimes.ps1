# Prepares the embedded Python and R for the SuiviEvalLab Windows installer.
#
#   pwsh tools/windows/prepare-runtimes.ps1
#
# Output: build/runtime/python and build/runtime/R, self-contained and relocatable.
# End users install nothing else. Versions are pinned here.

param(
  [string]$Out = "build/runtime",
  [string]$PythonVersion = "3.12.10",
  [string]$RVersion = "4.4.3",
  [string]$PythonHost = "python"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$root = Resolve-Path (Join-Path $PSScriptRoot "../..")
$out = Join-Path $root $Out
$cache = Join-Path $root "build/cache"
New-Item -ItemType Directory -Force -Path $out, $cache | Out-Null

function Get-File([string]$Url, [string]$Dest) {
  if (-not (Test-Path $Dest)) {
    Write-Host "Downloading $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Dest
  }
}

# --- Embedded Python ----------------------------------------------------------
$py = Join-Path $out "python"
if (-not (Test-Path (Join-Path $py "python.exe"))) {
  $zip = Join-Path $cache "python-$PythonVersion-embed-amd64.zip"
  Get-File "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip" $zip
  Expand-Archive -Path $zip -DestinationPath $py -Force
}
# Search paths: standard library, installed packages, SuiviEvalLab engine.
$pth = Get-ChildItem $py -Filter "python3*._pth" | Select-Object -First 1
$stdzip = (Get-ChildItem $py -Filter "python3*.zip" | Select-Object -First 1).Name
Set-Content -Path $pth.FullName -Encoding ascii -Value @($stdzip, ".", "Lib\site-packages", "..\engine\python")
$site = Join-Path $py "Lib\site-packages"
New-Item -ItemType Directory -Force -Path $site | Out-Null
& $PythonHost -m pip install --disable-pip-version-check --only-binary=:all: --upgrade --target $site -r (Join-Path $root "engine/python/requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Python package installation failed" }
& (Join-Path $py "python.exe") -c "import sys, polars; print('Python', sys.version.split()[0], 'polars', polars.__version__)"
if ($LASTEXITCODE -ne 0) { throw "Embedded Python is not usable" }

# --- Embedded R ----------------------------------------------------------------
$r = Join-Path $out "R"
$rscript = Join-Path $r "bin\Rscript.exe"
if (-not (Test-Path $rscript)) {
  $exe = Join-Path $cache "R-$RVersion-win.exe"
  Get-File "https://cloud.r-project.org/bin/windows/base/old/$RVersion/R-$RVersion-win.exe" $exe
  Write-Host "Silent install of R $RVersion into $r"
  $p = Start-Process -FilePath $exe -Wait -PassThru -ArgumentList @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/NOICONS",
    "/COMPONENTS=main,x64", "/DIR=`"$r`""
  )
  if ($p.ExitCode -ne 0) { throw "R installation failed (code $($p.ExitCode))" }
}
$rlib = (Join-Path $r "library") -replace "\\", "/"
$pkgs = (Get-Content (Join-Path $root "engine/r/packages.txt") | Where-Object { $_ -and -not $_.StartsWith("#") }) -join "','"
& $rscript --vanilla -e "options(repos = c(CRAN = 'https://cloud.r-project.org')); install.packages(c('$pkgs'), lib = '$rlib', type = 'win.binary', quiet = TRUE)"
if ($LASTEXITCODE -ne 0) { throw "R package installation failed" }
& $rscript --vanilla -e "for (p in c('$pkgs')) { library(p, character.only = TRUE, lib.loc = '$rlib'); cat(p, as.character(packageVersion(p, lib.loc = '$rlib')), '\n') }"
if ($LASTEXITCODE -ne 0) { throw "Missing R packages" }

# Trim: R documentation and tests are not used by the app.
foreach ($d in @("doc", "tests", "Tcl")) {
  $path = Join-Path $r $d
  if (Test-Path $path) { Remove-Item -Recurse -Force $path }
}
Get-ChildItem (Join-Path $r "library") -Directory | ForEach-Object {
  foreach ($d in @("doc", "html", "tests", "unitTests")) {
    $path = Join-Path $_.FullName $d
    if (Test-Path $path) { Remove-Item -Recurse -Force $path }
  }
}

Write-Host "Engines ready in $out"
