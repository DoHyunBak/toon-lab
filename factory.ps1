# Run from any working directory without virtual environment activation.
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    [Console]::Error.WriteLine("Project Python is missing: $pythonPath")
    [Console]::Error.WriteLine("From $projectRoot, run:")
    [Console]::Error.WriteLine('py -3 -m venv .venv')
    [Console]::Error.WriteLine('.\.venv\Scripts\python.exe -m pip install -r requirements.txt')
    exit 1
}
$factoryArguments = @($args)
if ($factoryArguments.Count -eq 0) {
    $factoryArguments = @('doctor')
}
$factoryExitCode = 1
Push-Location -LiteralPath $projectRoot
try {
    & $pythonPath -X utf8 -m src.factory @factoryArguments
    $factoryExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}
exit $factoryExitCode
