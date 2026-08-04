[CmdletBinding()]
param(
    [Parameter()]
    [string]$WorktreeRoot = "",

    [Parameter()]
    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-GitText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Repository,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    # Codex's Windows sandbox may run under a lower-privilege account than the
    # checkout owner.  Trust only this one explicit repository for this one
    # invocation; never mutate global safe.directory configuration.
    $output = & git -c "safe.directory=$Repository" -C $Repository @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git -C '$Repository' $($Arguments -join ' ') failed: $($output -join [Environment]::NewLine)"
    }
    return ($output -join [Environment]::NewLine).Trim()
}

function Resolve-FullPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path).Path)
}

function Test-SamePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Left,

        [Parameter(Mandatory = $true)]
        [string]$Right
    )

    return [string]::Equals(
        $Left.TrimEnd('\', '/'),
        $Right.TrimEnd('\', '/'),
        [StringComparison]::OrdinalIgnoreCase
    )
}

if ([string]::IsNullOrWhiteSpace($WorktreeRoot)) {
    $WorktreeRoot = Invoke-GitText -Repository (Get-Location).Path -Arguments @(
        "rev-parse", "--show-toplevel"
    )
}

if (-not (Test-Path -LiteralPath $WorktreeRoot -PathType Container)) {
    throw "worktree root does not exist: $WorktreeRoot"
}

$worktree = Resolve-FullPath -Path $WorktreeRoot
$reportedWorktree = Invoke-GitText -Repository $worktree -Arguments @(
    "rev-parse", "--show-toplevel"
)
$reportedWorktree = Resolve-FullPath -Path $reportedWorktree
if (-not (Test-SamePath -Left $worktree -Right $reportedWorktree)) {
    throw "requested root is not the Git worktree root: $worktree"
}

$commonGitDirectory = Invoke-GitText -Repository $worktree -Arguments @(
    "rev-parse", "--path-format=absolute", "--git-common-dir"
)
$commonGitDirectory = Resolve-FullPath -Path $commonGitDirectory
$sourceRoot = Resolve-FullPath -Path (Split-Path -Parent $commonGitDirectory)
$reportedSource = Invoke-GitText -Repository $sourceRoot -Arguments @(
    "rev-parse", "--show-toplevel"
)
$reportedSource = Resolve-FullPath -Path $reportedSource
if (-not (Test-SamePath -Left $sourceRoot -Right $reportedSource)) {
    throw "Git common directory does not resolve to the source checkout"
}

$isLocalCheckout = Test-SamePath -Left $worktree -Right $sourceRoot
if (-not $isLocalCheckout) {
    throw (
        "managed worktree dependency setup is disabled: the former junction " +
        "sharing design allowed host cleanup to erase Local .venv/reference " +
        "repositories; run dependency-backed tasks in the Local checkout"
    )
}

$lockPath = Join-Path $sourceRoot "repos.lock.json"
if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) {
    throw "repository lock is missing: $lockPath"
}
$repositoryLock = Get-Content -Raw -LiteralPath $lockPath | ConvertFrom-Json

$sharedPaths = [Collections.Generic.List[object]]::new()

$venvSource = Join-Path $sourceRoot ".venv"
$venvPython = Join-Path $venvSource "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw "source virtualenv Python is missing: $venvPython"
}

$shareSpecifications = [Collections.Generic.List[object]]::new()
$shareSpecifications.Add([pscustomobject]@{
    name = ".venv"
    relative_path = ".venv"
    expected_commit = $null
})

foreach ($repository in $repositoryLock.repositories) {
    $repositoryPath = [string]$repository.path
    $sourceRepository = Join-Path $sourceRoot $repositoryPath
    if (-not (Test-Path -LiteralPath $sourceRepository -PathType Container)) {
        throw "locked reference repository is missing: $sourceRepository"
    }

    if (-not $CheckOnly) {
        $actualCommit = Invoke-GitText -Repository $sourceRepository -Arguments @(
            "rev-parse", "HEAD"
        )
        if ($actualCommit -ne [string]$repository.commit) {
            throw "reference repository $($repository.name) is at $actualCommit, expected $($repository.commit)"
        }

        $dirtyState = Invoke-GitText -Repository $sourceRepository -Arguments @(
            "status", "--porcelain=v1", "--untracked-files=all"
        )
        if (-not [string]::IsNullOrWhiteSpace($dirtyState)) {
            throw "reference repository $($repository.name) is dirty; refusing to share it"
        }
    }

    $shareSpecifications.Add([pscustomobject]@{
        name = [string]$repository.name
        relative_path = $repositoryPath
        expected_commit = [string]$repository.commit
    })
}

foreach ($specification in $shareSpecifications) {
    $sourcePath = Resolve-FullPath -Path (Join-Path $sourceRoot $specification.relative_path)
    $sharedPaths.Add([pscustomobject]@{
        name = $specification.name
        status = "source"
        path = $sourcePath
        expected_commit = $specification.expected_commit
    })
}

$metadataSpecifications = @(
    [pscustomobject]@{
        relative_path = "artifacts\w3\legacy77_mapping.json"
        delivery = "included"
        snapshot_path = $null
        sha256 = "b6507dec2b564a0b5a06b185a4ce5070909194d5cf164edc503d840740b94ed3"
        size_bytes = 25173
    },
    [pscustomobject]@{
        relative_path = "artifacts\w3\model_graph.json"
        delivery = "included"
        snapshot_path = $null
        sha256 = "f030c5d4e43f63fbbcce771e4c4ea9e88b042be0a2c988e7f51de2c0e17ac410"
        size_bytes = 339932
    },
    [pscustomobject]@{
        relative_path = "artifacts\w3\golden_batch16\manifest.json"
        delivery = "restored"
        snapshot_path = "contracts\w3_metadata\golden_batch16_manifest.json.base64"
        sha256 = "f7e90cf1f087acf255e93d98d1788e0fb0b4c77bbe935ea9addb17feea583180"
        size_bytes = 170131
    },
    [pscustomobject]@{
        relative_path = "artifacts\w3\subop_batch16\manifest.json"
        delivery = "restored"
        snapshot_path = "contracts\w3_metadata\subop_batch16_manifest.json.base64"
        sha256 = "8bfdd042570408c1df793044407a8e6262bfa261b3cc6f02f64b94ad47d9c1c2"
        size_bytes = 49674
    }
)
$metadata = [Collections.Generic.List[object]]::new()

foreach ($specification in $metadataSpecifications) {
    $relativePath = [string]$specification.relative_path
    $metadataPath = Join-Path $worktree $relativePath
    if (-not (Test-Path -LiteralPath $metadataPath -PathType Leaf)) {
        if ($isLocalCheckout -or [string]$specification.delivery -ne "restored") {
            throw "worktree metadata is missing; check .worktreeinclude: $metadataPath"
        }

        $snapshotPath = Join-Path $worktree ([string]$specification.snapshot_path)
        if (-not (Test-Path -LiteralPath $snapshotPath -PathType Leaf)) {
            throw "tracked worktree metadata snapshot is missing: $snapshotPath"
        }
        try {
            $encodedSnapshot = (
                Get-Content -Raw -Encoding ASCII -LiteralPath $snapshotPath
            ) -replace '\s', ''
            $snapshotBytes = [Convert]::FromBase64String($encodedSnapshot)
        }
        catch {
            throw "tracked worktree metadata snapshot is invalid: $snapshotPath"
        }
        $snapshotHasher = [Security.Cryptography.SHA256]::Create()
        try {
            $snapshotHash = (
                [BitConverter]::ToString($snapshotHasher.ComputeHash($snapshotBytes))
            ).Replace('-', '').ToLowerInvariant()
        }
        finally {
            $snapshotHasher.Dispose()
        }
        if (
            $snapshotBytes.Length -ne [long]$specification.size_bytes -or
            $snapshotHash -ne [string]$specification.sha256
        ) {
            throw "tracked worktree metadata snapshot differs from the frozen W3 baseline: $snapshotPath"
        }

        if ($CheckOnly) {
            $metadata.Add([pscustomobject]@{
                relative_path = $relativePath.Replace('\', '/')
                status = "would_restore"
                sha256 = $snapshotHash
                size_bytes = $snapshotBytes.Length
            })
            continue
        }

        $metadataParent = Split-Path -Parent $metadataPath
        if (-not (Test-Path -LiteralPath $metadataParent -PathType Container)) {
            New-Item -ItemType Directory -Force -Path $metadataParent | Out-Null
        }
        [IO.File]::WriteAllBytes($metadataPath, $snapshotBytes)
    }

    $actualHash = (
        Get-FileHash -Algorithm SHA256 -LiteralPath $metadataPath
    ).Hash.ToLowerInvariant()
    if ($actualHash -ne [string]$specification.sha256) {
        throw "worktree metadata hash differs from the frozen W3 baseline: $metadataPath"
    }
    $actualSize = (Get-Item -LiteralPath $metadataPath).Length
    if ($actualSize -ne [long]$specification.size_bytes) {
        throw "worktree metadata size differs from the frozen W3 baseline: $metadataPath"
    }

    $metadata.Add([pscustomobject]@{
        relative_path = $relativePath.Replace('\', '/')
        status = if ($isLocalCheckout) { "source" } else { [string]$specification.delivery }
        sha256 = $actualHash
        size_bytes = $actualSize
    })
}

$repositoryVerification = "not_run"
if (-not $CheckOnly) {
    $worktreePython = Join-Path $worktree ".venv\Scripts\python.exe"
    $verifyScript = Join-Path $worktree "tools\sync_repositories.py"
    $verifyOutput = & $worktreePython $verifyScript verify 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "repository verification failed after setup: $($verifyOutput -join [Environment]::NewLine)"
    }
    $repositoryVerification = "passed"
}

[ordered]@{
    schema_version = "1.0"
    mode = if ($isLocalCheckout) { "local" } else { "worktree" }
    check_only = [bool]$CheckOnly
    worktree_root = $worktree
    source_root = $sourceRoot
    shared_paths = @($sharedPaths)
    metadata = @($metadata)
    repository_verify = $repositoryVerification
} | ConvertTo-Json -Depth 6
