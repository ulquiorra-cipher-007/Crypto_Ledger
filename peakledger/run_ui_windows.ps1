param(
    [switch]$debug,
    [switch]$cli
)

Set-Location $PSScriptRoot

$DEBUG_MODE = $debug -or $cli
$PYTHON_CMD = $null

if (-not $DEBUG_MODE) {
    if (Get-Command pythonw -ErrorAction SilentlyContinue) {
        $PYTHON_CMD = "pythonw"
    } elseif (Get-Command pyw -ErrorAction SilentlyContinue) {
        $PYTHON_CMD = "pyw"
    } else {
        $appdata = [Environment]::GetFolderPath("LocalApplicationData")
        $paths = @(
            "$appdata\Programs\Python\Python312\pythonw.exe",
            "$appdata\Programs\Python\Python313\pythonw.exe",
            "$appdata\Programs\Python\Python310\pythonw.exe",
            "C:\Python312\pythonw.exe",
            "C:\Python313\pythonw.exe"
        )
        foreach ($p in $paths) {
            if (Test-Path $p) {
                $PYTHON_CMD = $p
                break
            }
        }
    }
}

if (-not $PYTHON_CMD) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $PYTHON_CMD = "python"
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $PYTHON_CMD = "py"
    } else {
        [System.Windows.Forms.MessageBox]::Show("Python was not found.", "PeakLedger Startup Error", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)
        exit 1
    }
}

$argsList = @("ui\main.py")
if ($cli) { $argsList += "--cli" }

if ($DEBUG_MODE) {
    & $PYTHON_CMD $argsList
} else {
    Start-Process -NoNewWindow -FilePath $PYTHON_CMD -ArgumentList $argsList
}
