$ErrorActionPreference = "Stop"

if ($env:CANOPYGUARD_PYTHON) {
    $Python = $env:CANOPYGUARD_PYTHON
} else {
    $Python = "python"
}

function Invoke-Checked {
    param([string[]]$CommandArgs)

    & $Python @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Invoke-Checked @("-m", "ruff", "check", ".")
Invoke-Checked @("-m", "ruff", "format", "--check", ".")
Invoke-Checked @("scripts/check_text_hygiene.py")
Invoke-Checked @("-m", "pytest")
Invoke-Checked @("-m", "pip", "check")
Invoke-Checked @("-m", "compileall", "-q", "src", "tests", "scripts")
