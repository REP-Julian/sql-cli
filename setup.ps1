$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ModelName = 'qwen2.5-coder:3b'
$XamppUrl = 'https://www.apachefriends.org/download.html'
$OllamaInstallUrl = 'https://ollama.com/install.ps1'

function Ask-YesNo([string]$Prompt, [bool]$DefaultYes = $true) {
    $suffix = if ($DefaultYes) { '[Y/n]' } else { '[y/N]' }
    $answer = Read-Host "$Prompt $suffix"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $DefaultYes }
    return $answer.Trim().ToLowerInvariant() -in @('y', 'yes')
}

function Open-DownloadPage([string]$Url, [string]$Product) {
    if (Ask-YesNo "$Product was not found. Open its official download page now?" $true) {
        Start-Process $Url
        Write-Host "Install $Product, then run setup.bat again." -ForegroundColor Yellow
    } else {
        Write-Host "$Product was skipped. SQLCLI can still be installed, but that feature will not work yet." -ForegroundColor Yellow
    }
}

function Find-Xampp {
    $candidates = @()
    if ($env:XAMPP_HOME) { $candidates += $env:XAMPP_HOME }
    $candidates += @('C:\xampp', 'C:\Program Files\xampp', 'C:\Program Files (x86)\xampp')
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-Path -LiteralPath (Join-Path $candidate 'mysql\bin\mysqld.exe')) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

function Set-EnvFileValue([string]$Path, [string]$Name, [string]$Value) {
    $lines = [System.Collections.Generic.List[string]]::new()
    if (Test-Path -LiteralPath $Path) {
        foreach ($line in [System.IO.File]::ReadAllLines($Path)) { $lines.Add($line) }
    }
    $pattern = '^\s*' + [regex]::Escape($Name) + '\s*='
    $found = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match $pattern) {
            $lines[$index] = "$Name=$Value"
            $found = $true
        }
    }
    if (-not $found) { $lines.Add("$Name=$Value") }
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllLines($Path, $lines, $utf8NoBom)
}

function Get-EnvFileValue([string]$Path, [string]$Name, [string]$Fallback) {
    if (Test-Path -LiteralPath $Path) {
        $pattern = '^\s*' + [regex]::Escape($Name) + '\s*=\s*(.*?)\s*$'
        foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
            if ($line -match $pattern) { return $Matches[1].Trim('"', "'") }
        }
    }
    return $Fallback
}

function Test-LocalPort([string]$HostName, [int]$Port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync($HostName, $Port)
        return $task.Wait(1500) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Find-Ollama {
    $candidates = @(
        (Join-Path $Root 'ollama\ollama.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'),
        (Join-Path $env:LOCALAPPDATA 'Ollama\ollama.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    $command = Get-Command ollama -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    return $null
}

function Get-ResourceSnapshot {
    # Win32_Processor.LoadPercentage is a lightweight system-wide CPU sample.
    # Fail closed: if Windows cannot provide a CPU reading, skip optional AI setup.
    try {
        $processors = @(Get-CimInstance -ClassName Win32_Processor -ErrorAction Stop)
        $loads = @($processors | ForEach-Object { $_.LoadPercentage } | Where-Object { $null -ne $_ })
        if ($loads.Count -eq 0) { return $null }
        $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
        $freeGb = $os.FreePhysicalMemory / 1MB
        return [pscustomobject]@{
            CpuPercent = [math]::Round((($loads | Measure-Object -Average).Average), 0)
            AvailableGb = $freeGb
        }
    } catch {
        return $null
    }
}

function Test-AiResourceBudget([string]$Stage) {
    $snapshot = Get-ResourceSnapshot
    if ($null -eq $snapshot) {
        Write-Host "Skipping optional Ollama/model setup: Windows could not safely read CPU and memory usage before $Stage." -ForegroundColor Yellow
        return $false
    }
    Write-Host ("Resource check before {0}: CPU {1}%, free RAM {2:N1} GB." -f $Stage, $snapshot.CpuPercent, $snapshot.AvailableGb)
    if ($snapshot.CpuPercent -ge 60 -or $snapshot.AvailableGb -lt 4.0) {
        Write-Host ("Skipping optional Ollama/model setup to protect your laptop. It needs CPU below 60% and at least 4.0 GB free RAM; current values are CPU {0}% and {1} GB free. Run setup.bat again when the laptop is less busy." -f $snapshot.CpuPercent, $snapshot.AvailableGb) -ForegroundColor Yellow
        return $false
    }
    return $true
}

try {
    Set-Location -LiteralPath $Root
    Write-Host ''
    Write-Host 'SQLCLI Workbench setup' -ForegroundColor Cyan
    Write-Host "Project folder: $Root"
    Write-Host 'This setup preserves an existing .env file and asks before installing optional applications or a model.'
    Write-Host ''

    $XamppPath = Find-Xampp
    if (-not $XamppPath) {
        Open-DownloadPage 'https://www.apachefriends.org/download.html' 'XAMPP'
    } else {
        Write-Host "XAMPP found: $XamppPath" -ForegroundColor Green
    }

    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        & $PyLauncher.Source -3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) {
            $PythonExe = $PyLauncher.Source
            $PythonPrefix = @('-3')
        } else { $PyLauncher = $null }
    }
    if (-not $PyLauncher -and $PythonCommand) {
        & $PythonCommand.Source -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) {
            $PythonExe = $PythonCommand.Source
            $PythonPrefix = @()
        } else { $PythonCommand = $null }
    }
    if (-not $PythonExe) {
        Open-DownloadPage 'https://www.python.org/downloads/windows/' 'Python 3.10 or newer'
        throw 'Python 3.10 or newer is required. Install it, then rerun setup.bat.'
    }
    Write-Host 'Python 3.10 or newer found.' -ForegroundColor Green

    $VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        Write-Host 'Creating a project-only Python environment...'
        & $PythonExe @PythonPrefix -m venv (Join-Path $Root '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }
    Write-Host 'Installing SQLCLI and its Python packages...'
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Could not update pip.' }
    & $VenvPython -m pip install -e $Root
    if ($LASTEXITCODE -ne 0) { throw 'Could not install SQLCLI dependencies.' }

    $EnvPath = Join-Path $Root '.env'
    if (-not (Test-Path -LiteralPath $EnvPath)) {
        Copy-Item -LiteralPath (Join-Path $Root '.env.example') -Destination $EnvPath
        Set-EnvFileValue $EnvPath 'SQLCLI_AI_ENABLED' 'true'
        Write-Host 'Created .env from the safe example settings.' -ForegroundColor Green
    } else {
        Write-Host 'Existing .env found; keeping its database settings and credentials.' -ForegroundColor Green
        if ((Get-EnvFileValue $EnvPath 'SQLCLI_AI_ENABLED' 'false').ToLowerInvariant() -notin @('1','true','yes','on')) {
            if (Ask-YesNo 'Enable optional local AI in this project .env?' $true) {
                Set-EnvFileValue $EnvPath 'SQLCLI_AI_ENABLED' 'true'
            }
        }
    }
    $ModelName = Get-EnvFileValue $EnvPath 'SQLCLI_OLLAMA_MODEL' $ModelName

    $OllamaExe = Find-Ollama
    $AiSetupAllowed = Test-AiResourceBudget 'optional Ollama setup'
    if ($AiSetupAllowed) {
        if (-not $OllamaExe) {
            if (Ask-YesNo 'Ollama was not found. Download and install it into this project folder?' $true) {
                $OllamaDir = Join-Path $Root 'ollama'
                $ModelsDir = Join-Path $Root 'models'
                New-Item -ItemType Directory -Force -Path $OllamaDir, $ModelsDir | Out-Null
                $env:OLLAMA_INSTALL_DIR = $OllamaDir
                $env:OLLAMA_MODELS = $ModelsDir
                $env:OLLAMA_DEBUG = '1'
                $InstallerPath = Join-Path $env:TEMP 'sqlcli-ollama-install.ps1'
                Write-Host 'Downloading the official Ollama installer...'
                Invoke-WebRequest -Uri $OllamaInstallUrl -OutFile $InstallerPath
                if (Test-AiResourceBudget 'installing Ollama') {
                    Write-Host 'Installing Ollama. This can take a few minutes...'
                    & $InstallerPath
                    $OllamaExe = Find-Ollama
                }
            }
        }

        if ($OllamaExe) {
            $ModelsDir = Join-Path $Root 'models'
            New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null
            Set-EnvFileValue $EnvPath 'SQLCLI_OLLAMA_BIN' $OllamaExe
            Set-EnvFileValue $EnvPath 'SQLCLI_OLLAMA_MODELS' $ModelsDir
            $env:OLLAMA_MODELS = $ModelsDir
            $env:OLLAMA_MAX_LOADED_MODELS = '1'
            $env:OLLAMA_NUM_PARALLEL = '1'
            $ExistingModelPath = [Environment]::GetEnvironmentVariable('OLLAMA_MODELS', 'User')
            if ([string]::IsNullOrWhiteSpace($ExistingModelPath) -or $ExistingModelPath.TrimEnd('\') -eq $ModelsDir.TrimEnd('\')) {
                [Environment]::SetEnvironmentVariable('OLLAMA_MODELS', $ModelsDir, 'User')
            } elseif (Ask-YesNo "Your user OLLAMA_MODELS points to '$ExistingModelPath'. Change it to this project's models folder?" $false) {
                [Environment]::SetEnvironmentVariable('OLLAMA_MODELS', $ModelsDir, 'User')
            }

            $apiReady = $false
            try { $null = Invoke-RestMethod 'http://localhost:11434/api/version' -TimeoutSec 2; $apiReady = $true } catch { }
            $serviceStartAllowed = $apiReady -or (Test-AiResourceBudget 'starting the Ollama service')
            if (-not $apiReady -and $serviceStartAllowed) {
                Write-Host 'Starting the local Ollama service...'
                Start-Process -FilePath $OllamaExe -ArgumentList 'serve' -WindowStyle Hidden
                for ($try = 0; $try -lt 20; $try++) {
                    Start-Sleep -Milliseconds 750
                    try { $null = Invoke-RestMethod 'http://localhost:11434/api/version' -TimeoutSec 2; $apiReady = $true; break } catch { }
                }
            }
            if ($apiReady) {
                $modelFound = $false
                try {
                    $tags = Invoke-RestMethod 'http://localhost:11434/api/tags' -TimeoutSec 4
                    $modelFound = [bool]($tags.models | Where-Object { $_.name -eq $ModelName })
                } catch { }
                if (-not $modelFound -and (Ask-YesNo "Download the local SQL assistant model $ModelName? (about 1.9 GB for the default model)" $true)) {
                    if (Test-AiResourceBudget "downloading $ModelName") {
                        Write-Host "Downloading $ModelName. Keep this window open until it finishes..."
                        & $OllamaExe pull $ModelName
                        if ($LASTEXITCODE -ne 0) { throw "Ollama could not download $ModelName." }
                    }
                }
                try {
                    $tags = Invoke-RestMethod 'http://localhost:11434/api/tags' -TimeoutSec 4
                    if ($tags.models | Where-Object { $_.name -eq $ModelName }) {
                        Write-Host "Ollama and $ModelName are ready." -ForegroundColor Green
                    } else {
                        Write-Host "The model is not installed yet. Inside SQLCLI run :ollama pull when you are ready." -ForegroundColor Yellow
                    }
                } catch { }
            } elseif (-not $apiReady -and $serviceStartAllowed) {
                Write-Host 'Ollama is installed but its local API did not start. You can retry later with :ollama start.' -ForegroundColor Yellow
            } elseif (-not $apiReady) {
                Write-Host 'Ollama service start was skipped because of the resource check. Run setup.bat again later.' -ForegroundColor Yellow
            }
        } else {
            Write-Host 'Ollama setup was skipped; local AI will not be available until Ollama is installed.' -ForegroundColor Yellow
        }
    } else {
        Write-Host 'The SQLCLI and database setup can continue. Rerun setup.bat later to retry optional Ollama and model setup.' -ForegroundColor Yellow
    }

    if ($XamppPath) {
        $MysqlHost = Get-EnvFileValue $EnvPath 'MYSQL_HOST' '127.0.0.1'
        $MysqlPort = [int](Get-EnvFileValue $EnvPath 'MYSQL_PORT' '3306')
        if (Test-LocalPort $MysqlHost $MysqlPort) {
            Write-Host "MySQL is responding at ${MysqlHost}:$MysqlPort." -ForegroundColor Green
        } else {
            Write-Host "MySQL is not responding at ${MysqlHost}:$MysqlPort yet." -ForegroundColor Yellow
            $ControlPanel = Join-Path $XamppPath 'xampp-control.exe'
            if ((Test-Path -LiteralPath $ControlPanel) -and (Ask-YesNo 'Open the XAMPP Control Panel so you can start MySQL?' $true)) {
                Start-Process -FilePath $ControlPanel
            }
            Write-Host 'Click Start next to MySQL. Then open SQLCLI and use :connect if needed.'
        }
    }

    Write-Host ''
    Write-Host 'Setup complete.' -ForegroundColor Green
    Write-Host 'Start MySQL in XAMPP, then run:'
    Write-Host '  .\.venv\Scripts\sqlcli.exe'
    Write-Host 'Inside SQLCLI, use :databases, then :use your_database_name.'
    if ($OllamaExe) { Write-Host 'For AI, use :ollama status and :ask <your question>.' }
    Write-Host 'See README.md for the full beginner guide and troubleshooting.'
} catch {
    Write-Host "`nSetup error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
