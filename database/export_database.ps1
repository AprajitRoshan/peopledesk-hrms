$ErrorActionPreference = "Stop"
$databaseName = "hrms_db"
$databaseHost = "127.0.0.1"
$databasePort = "3306"
$databaseUser = "root"
$outputPath = Join-Path $PSScriptRoot "hrms_db_dump.sql"

$dumpCommand = Get-Command mysqldump -ErrorAction SilentlyContinue
if (-not $dumpCommand) {
    throw "mysqldump was not found on PATH. Add your MySQL Server bin directory to PATH, then rerun this script."
}

Write-Host "Exporting $databaseName to $outputPath. MySQL will prompt for the password."
& $dumpCommand.Source --host=$databaseHost --port=$databasePort --user=$databaseUser --password --single-transaction --routines --triggers --databases $databaseName --result-file=$outputPath
if ($LASTEXITCODE -ne 0) {
    Remove-Item $outputPath -ErrorAction SilentlyContinue
    throw "mysqldump failed with exit code $LASTEXITCODE. Check credentials and database access."
}
Write-Host "Database export completed. Keep the dump private and do not commit it to a public repository."
