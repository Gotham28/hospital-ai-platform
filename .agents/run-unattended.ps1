$repo = "D:\Hospital\hospital-ai-platform"
Set-Location $repo
New-Item -ItemType Directory -Force -Path "$repo\.agents\runs" | Out-Null
$log = "$repo\.agents\runs\run-$(Get-Date -Format yyyyMMdd-HHmm).log"

$prompt = @"
/drive

I am away and cannot answer questions. Follow the drive skill exactly.
Never merge a pull request. Never run an Alembic or database command.
If anything is ambiguous, stop and write to .agents/handoff.md rather than guessing.
"@

claude -p $prompt --permission-mode auto --model sonnet 2>&1 |
    Tee-Object -FilePath $log
Write-Host "`nLog written to $log"