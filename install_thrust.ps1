$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPath = Join-Path $RepoRoot '.venv'

function Write-Step([string]$Message) {
    Write-Host "`n[THRUST] $Message" -ForegroundColor Cyan
}

function Add-PythonCandidate($List, [version]$Version, [string]$Path) {
    if ($Version.Major -eq 3 -and $Version.Minor -ge 11 -and (Test-Path $Path)) {
        $List.Add([pscustomobject]@{ Version = $Version; Path = $Path })
    }
}

try {
    Write-Step "Repository: $RepoRoot"
    $candidates = [System.Collections.Generic.List[object]]::new()

    $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        Write-Step 'Searching Python installations registered with the Python launcher (py -0p)...'
        $launcherOutput = & $pyLauncher.Source -0p 2>&1
        foreach ($line in $launcherOutput) {
            if ([string]$line -match '(?<major>\d+)\.(?<minor>\d+).*?(?<path>[A-Za-z]:\\.*?python(?:\.exe)?)\s*$') {
                $version = [version]::new([int]$Matches.major, [int]$Matches.minor)
                Add-PythonCandidate $candidates $version $Matches.path.Trim()
            }
        }
    }

    foreach ($commandName in @('python.exe', 'python3.exe', 'python')) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $command) { continue }
        $pythonPath = $command.Source
        try {
            $versionText = & $pythonPath -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>$null
            $version = [version]::Parse(([string]$versionText).Trim())
            Add-PythonCandidate $candidates $version $pythonPath
        } catch { }
    }

    $selected = $candidates | Sort-Object Version -Descending | Select-Object -First 1
    if (-not $selected) {
        throw 'No supported Python 3.11+ installation was found. Install Python from python.org with the Python launcher, then run this installer again.'
    }
    Write-Step "Selected Python $($selected.Version) at $($selected.Path)"

    if (-not (Test-Path (Join-Path $VenvPath 'Scripts\python.exe'))) {
        Write-Step 'Creating an isolated .venv in the repository...'
        & $selected.Path -m venv $VenvPath
        if ($LASTEXITCODE -ne 0) { throw 'Python could not create the virtual environment.' }
    } else {
        Write-Step 'Using the existing .venv in the repository.'
    }

    $venvPython = Join-Path $VenvPath 'Scripts\python.exe'
    $guiLauncher = Join-Path $VenvPath 'Scripts\thrust-measure.exe'
    Write-Step 'Updating pip and installing THRUST-measure with its GUI dependencies from pyproject.toml...'
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Could not upgrade pip.' }
    & $venvPython -m pip install -e '.[gui]' --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    if (-not (Test-Path $guiLauncher)) { throw 'The GUI launcher was not installed. Check the [project.gui-scripts] entry in pyproject.toml.' }

    Write-Step 'Creating a desktop shortcut that starts the GUI without a Command Prompt window...'
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shortcutPath = Join-Path $desktop 'THRUST-measure.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $guiLauncher
    $shortcut.Arguments = ''
    $shortcut.WorkingDirectory = $RepoRoot
    $iconPath = Join-Path $RepoRoot 'THRUST.ico'
    if (Test-Path -LiteralPath $iconPath) {
        $shortcut.IconLocation = "$iconPath,0"
    } else {
        $shortcut.IconLocation = "$guiLauncher,0"
        Write-Step 'THRUST.ico was not found; using the default application icon.'
    }
    $shortcut.Description = 'Start THRUST-measure'
    $shortcut.Save()

    Write-Host "`nInstallation complete." -ForegroundColor Green
    Write-Host "Virtual environment: $VenvPath"
    Write-Host "Desktop shortcut:   $shortcutPath"
    Write-Host 'The shortcut uses the Windows GUI entry point, so no console window opens.'
    exit 0
} catch {
    Write-Host "`nERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
