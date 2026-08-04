param(
    [Parameter(Mandatory = $true)]
    [string]$RtlRoot,
    [string]$Top = "NDP_Top_phy",
    [string]$RootFilelist = "NDP_Top_phy_filelist.f",
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [string]$Iverilog = "C:\iverilog\bin\iverilog.exe"
)

$ErrorActionPreference = "Stop"
$rtl = (Resolve-Path -LiteralPath $RtlRoot).Path
$filelistRoot = Join-Path $rtl "filelists"
$entry = (Resolve-Path -LiteralPath (Join-Path $filelistRoot $RootFilelist)).Path
$mcDir = Join-Path $rtl "DDR_Model\MC_IP\rtl"
$out = [System.IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Path $out -Force | Out-Null

$sources = [System.Collections.Generic.List[string]]::new()
$includeDirs = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)
$defines = [System.Collections.Generic.List[string]]::new()
$seenFilelists = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)

function Expand-AuditVariable {
    param([string]$Value)
    return $Value.Replace('$MC_DIR', $mcDir)
}

function Read-AuditFilelist {
    param([string]$Path)
    $expandedPath = Expand-AuditVariable $Path
    $resolved = (Resolve-Path -LiteralPath $expandedPath).Path
    if (-not $seenFilelists.Add($resolved)) {
        return
    }
    $base = Split-Path -Parent $resolved
    foreach ($raw in Get-Content -LiteralPath $resolved) {
        $line = (Expand-AuditVariable $raw.Trim())
        if (-not $line -or $line.StartsWith("#")) {
            continue
        }
        if ($line -match '^\+incdir\+(.+)$') {
            $pathValue = $Matches[1]
            if (-not [System.IO.Path]::IsPathRooted($pathValue)) {
                $pathValue = Join-Path $base $pathValue
            }
            $includeDirs.Add([System.IO.Path]::GetFullPath($pathValue)) | Out-Null
            continue
        }
        if ($line -match '^-[Ff]\s+(.+)$') {
            $pathValue = $Matches[1]
            if (-not [System.IO.Path]::IsPathRooted($pathValue)) {
                $pathValue = Join-Path $base $pathValue
            }
            Read-AuditFilelist $pathValue
            continue
        }
        if ($line -match '^\+define\+(.+)$') {
            $defines.Add($Matches[1]) | Out-Null
            continue
        }
        if ($line -match '\.(sv|v|svh|vh|vp)$') {
            $pathValue = $line
            if (-not [System.IO.Path]::IsPathRooted($pathValue)) {
                $pathValue = Join-Path $base $pathValue
            }
            $pathValue = [System.IO.Path]::GetFullPath($pathValue)
            if (-not (Test-Path -LiteralPath $pathValue)) {
                throw "Missing source '$pathValue' referenced by '$resolved'"
            }
            $sources.Add($pathValue) | Out-Null
        }
    }
}

Read-AuditFilelist $entry

$normalized = Join-Path $out "normalized_iverilog_filelist.f"
$normalizedLines = [System.Collections.Generic.List[string]]::new()
foreach ($inc in ($includeDirs | Sort-Object)) {
    $normalizedLines.Add("+incdir+$inc") | Out-Null
}
foreach ($define in $defines) {
    $normalizedLines.Add("+define+$define") | Out-Null
}
foreach ($source in $sources) {
    $normalizedLines.Add($source) | Out-Null
}
[System.IO.File]::WriteAllLines(
    $normalized,
    $normalizedLines,
    [System.Text.UTF8Encoding]::new($false)
)

$savedErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$compilerOutput = & $Iverilog -g2012 -i -tnull -s $Top -f $normalized 2>&1
$compilerExit = $LASTEXITCODE
$ErrorActionPreference = $savedErrorActionPreference
$log = Join-Path $out "iverilog_compile.log"
[System.IO.File]::WriteAllLines(
    $log,
    [string[]]$compilerOutput,
    [System.Text.UTF8Encoding]::new($false)
)

$report = [ordered]@{
    schema = "rtl-filelist-compile-audit-v1"
    rtl_root = $rtl
    top = $Top
    root_filelist = $entry
    parsed_filelists = $seenFilelists.Count
    source_entries = $sources.Count
    unique_source_entries = @($sources | Sort-Object -Unique).Count
    include_dirs = $includeDirs.Count
    defines = $defines.Count
    compiler = (Resolve-Path -LiteralPath $Iverilog).Path
    compiler_exit = $compilerExit
    compile_passed = ($compilerExit -eq 0)
    normalized_filelist = $normalized
    compile_log = $log
}
$reportPath = Join-Path $out "report.json"
[System.IO.File]::WriteAllText(
    $reportPath,
    ($report | ConvertTo-Json -Depth 5),
    [System.Text.UTF8Encoding]::new($false)
)
$report | ConvertTo-Json -Depth 5
exit $compilerExit
