<#
.SYNOPSIS
  Opens a workbook in a NEW Tableau Desktop process, reports whether it loads, then closes that process.

.DESCRIPTION
  Pass  : the Tableau window title shows the workbook name and no error dialog is present.
  Fail  : Tableau shows a load error; the full error text is captured with the dialog's
          "Copy Error Message" button (the clipboard's previous text is restored afterwards).
  Timeout: neither happened within -TimeoutSec.
  Only the Tableau process started here is closed; other Tableau windows are left alone.
  Output is one JSON object on stdout. Exit code: 0 pass, 1 fail, 2 timeout/other.
#>
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [int]$TimeoutSec = 150,
    [string]$TableauExe = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes

if (-not $TableauExe) {
    $TableauExe = Get-ChildItem "C:\Program Files\Tableau\Tableau *\bin\tableau.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $TableauExe -or -not (Test-Path $TableauExe)) {
    @{ status = "unavailable"; details = "Tableau Desktop not found" } | ConvertTo-Json -Compress
    exit 2
}
$full = (Resolve-Path $Path).Path
$stem = [IO.Path]::GetFileNameWithoutExtension($full)

$A = [System.Windows.Automation.AutomationElement]
$Scope = [System.Windows.Automation.TreeScope]

function Get-ProcessWindows([int]$procId) {
    $cond = New-Object System.Windows.Automation.PropertyCondition($A::ProcessIdProperty, $procId)
    try { return $A::RootElement.FindAll($Scope::Children, $cond) } catch { return @() }
}

function Find-ByName($element, [string]$name) {
    $cond = New-Object System.Windows.Automation.PropertyCondition($A::NameProperty, $name)
    return $element.FindFirst($Scope::Descendants, $cond)
}

function Get-ErrorText($window) {
    # Windows can appear or disappear mid-scan while Tableau loads; treat that as "nothing yet".
    try {
        $texts = $window.FindAll($Scope::Descendants, [System.Windows.Automation.Condition]::TrueCondition) |
            ForEach-Object { try { $_.Current.Name } catch { $null } } | Where-Object { $_ }
    } catch { return $null }
    if (-not ($texts | Where-Object { $_ -like "Error Code:*" -or $_ -like "Errors occurred*" })) { return $null }
    $summary = ($texts | Where-Object { $_ -like "Errors occurred*" -or $_ -like "Error Code:*" -or $_ -like "Unable to*" }) -join "`n"
    $detail = ""
    $copy = Find-ByName $window "Copy Error Message"
    if ($copy) {
        $previous = $null
        try { $previous = Get-Clipboard -Raw } catch {}
        try {
            $pattern = $copy.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
            $pattern.Invoke()
            Start-Sleep -Milliseconds 700
            $detail = Get-Clipboard -Raw
        } catch {}
        if ($null -ne $previous) { try { Set-Clipboard -Value $previous } catch {} }
    }
    if ($detail) { return $detail }
    return $summary
}

$startTime = (Get-Date).AddSeconds(-2)
$proc = Start-Process -FilePath $TableauExe -ArgumentList "`"$full`"" -PassThru
$deadline = (Get-Date).AddSeconds($TimeoutSec)
$result = @{ status = "timeout"; details = "no load result within $TimeoutSec s"; pid = $proc.Id }
try {
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        $proc.Refresh()
        if ($proc.HasExited) { $result = @{ status = "fail"; details = "Tableau exited"; pid = $proc.Id }; break }
        $errorText = $null
        foreach ($w in (Get-ProcessWindows $proc.Id)) {
            $errorText = Get-ErrorText $w
            if ($errorText) { break }
        }
        if ($errorText) { $result = @{ status = "fail"; details = $errorText; pid = $proc.Id }; break }
        if ($proc.MainWindowTitle -like "*$stem*") {
            Start-Sleep -Seconds 4   # let any post-load warning dialog appear
            foreach ($w in (Get-ProcessWindows $proc.Id)) {
                $errorText = Get-ErrorText $w
                if ($errorText) { break }
            }
            if ($errorText) { $result = @{ status = "fail"; details = $errorText; pid = $proc.Id }; break }
            # Query errors do not always raise a dialog; read this process's Tableau log as well.
            Start-Sleep -Seconds 6
            $logDir = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "My Tableau Repository\Logs"
            $queryErrors = @()
            Get-ChildItem $logDir -Filter "log*.txt" -File -ErrorAction SilentlyContinue |
                Where-Object { $_.LastWriteTime -ge $startTime } | ForEach-Object {
                    $queryErrors += Select-String -Path $_.FullName -SimpleMatch -Pattern "`"pid`":$($proc.Id)," |
                        Where-Object { $_.Line -match 'LogicalQueryException|"batch-errors":true|qp-process-query-error' } |
                        ForEach-Object { if ($_.Line -match '"msg":"\\"([^"]+)') { $Matches[1] } elseif ($_.Line -match '"error-messages":"([^"]+)') { $Matches[1] } else { $_.Line.Substring(0, [Math]::Min(300, $_.Line.Length)) } }
                }
            $queryErrors = $queryErrors | Select-Object -Unique
            if ($queryErrors) { $result = @{ status = "fail"; details = ($queryErrors -join "`n"); pid = $proc.Id } }
            else { $result = @{ status = "pass"; details = $proc.MainWindowTitle; pid = $proc.Id } }
            break
        }
    }
} finally {
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
}
$result | ConvertTo-Json -Compress
switch ($result.status) { "pass" { exit 0 } "fail" { exit 1 } default { exit 2 } }
