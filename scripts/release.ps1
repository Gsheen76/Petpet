param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')]
    [string]$Version
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$Tag = "v$Version"
$releaseNotes = Join-Path $projectRoot "docs\RELEASE_NOTES_v$Version.md"
$releaseDir = Join-Path $projectRoot "dist\release-$Tag"
$exePath = Join-Path $projectRoot "dist\Petpet.exe"
$windowsZipName = "Petpet-v$Version-windows.zip"
$windowsZipPath = Join-Path $projectRoot "dist\$windowsZipName"
$checksumName = "Petpet-v$Version-SHA256SUMS.txt"
$checksumPath = Join-Path $projectRoot "dist\$checksumName"
$GhCommand = "gh"
$originalGhTokenExists = Test-Path Env:GH_TOKEN
$originalGhToken = $env:GH_TOKEN
$releaseExitCode = 0
$requiredAssetNames = @(
    "Petpet.exe",
    "Petpet-v$Version-windows.zip",
    "Petpet-v$Version-macOS-arm64.zip",
    "Petpet-v$Version-macOS-intel.zip"
)

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Invoke-Native([string]$Command, [string[]]$Arguments) {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE."
    }
}

function Get-CommandText([string]$Command, [string[]]$Arguments) {
    $output = & $Command @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return ($output -join "`n").Trim()
}

function Get-ReleaseInfo {
    $json = Get-CommandText $GhCommand @(
        "release", "view", $Tag, "--json",
        "isDraft,isPrerelease,tagName,targetCommitish,url,assets"
    )
    if (-not $json) {
        return $null
    }
    return $json | ConvertFrom-Json
}

function Get-ReleaseAssets {
    $release = Get-ReleaseInfo
    if ($null -eq $release) {
        return @()
    }
    return @($release.assets)
}

function Get-MissingReleaseAssets {
    $assets = Get-ReleaseAssets
    $missing = @()
    foreach ($name in $requiredAssetNames) {
        $asset = $assets | Where-Object { $_.name -eq $name } | Select-Object -First 1
        if ($null -eq $asset -or $asset.state -ne "uploaded" -or
            [int64]$asset.size -le 0) {
            $missing += $name
        }
    }
    return $missing
}

function Compare-RemoteAssetHash([string]$AssetName, [string]$LocalPath) {
    $downloadRoot = Join-Path $releaseDir ("verify-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $downloadRoot | Out-Null
    try {
        Invoke-Native $GhCommand @(
            "release", "download", $Tag, "--pattern", $AssetName,
            "--dir", $downloadRoot
        )
        $downloadedPath = Join-Path $downloadRoot $AssetName
        if (-not (Test-Path -LiteralPath $downloadedPath -PathType Leaf)) {
            throw "Release download did not produce $AssetName."
        }
        $localHash = (Get-FileHash -LiteralPath $LocalPath -Algorithm SHA256).Hash
        $remoteHash = (Get-FileHash -LiteralPath $downloadedPath -Algorithm SHA256).Hash
        return $localHash -eq $remoteHash
    } finally {
        if (Test-Path -LiteralPath $downloadRoot) {
            Remove-Item -LiteralPath $downloadRoot -Recurse -Force
        }
    }
}

function Stop-ProcessTree([int]$ProcessId) {
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" `
        -ErrorAction SilentlyContinue)
    foreach ($child in $children) {
        Stop-ProcessTree ([int]$child.ProcessId)
    }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

function Verify-RemoteRefs([string]$ExpectedCommit) {
    $remoteMainLine = @(git ls-remote origin refs/heads/main)
    if ($LASTEXITCODE -ne 0 -or $remoteMainLine.Count -ne 1) {
        throw "Unable to verify remote main."
    }
    $remoteTagLine = @(git ls-remote origin "refs/tags/$Tag^{}")
    if ($LASTEXITCODE -ne 0 -or $remoteTagLine.Count -ne 1) {
        throw "Unable to verify the peeled remote release tag."
    }
    $remoteMain = ($remoteMainLine[0] -split "\s+")[0]
    $remoteTag = ($remoteTagLine[0] -split "\s+")[0]
    if ($remoteMain -ne $ExpectedCommit -or $remoteTag -ne $ExpectedCommit) {
        throw "Remote main, tag, and expected commit differ."
    }
}

function Verify-PublishedRelease([string]$ExpectedCommit) {
    $release = Get-ReleaseInfo
    if ($null -eq $release -or $release.tagName -ne $Tag -or
        $release.isDraft -or $release.isPrerelease) {
        throw "Published Release metadata is invalid."
    }
    Verify-RemoteRefs $ExpectedCommit
    $finalRoot = Join-Path $releaseDir ("final-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $finalRoot | Out-Null
    try {
        foreach ($name in $requiredAssetNames) {
            $asset = @($release.assets | Where-Object { $_.name -eq $name })
            if ($asset.Count -ne 1 -or $asset[0].state -ne "uploaded" -or
                [int64]$asset[0].size -le 0 -or
                $asset[0].url -notlike "*/releases/download/$Tag/$name") {
                throw "Final asset failed metadata verification: $name"
            }
            Invoke-Native $GhCommand @(
                "release", "download", $Tag, "--pattern", $name, "--dir", $finalRoot
            )
            $path = Join-Path $finalRoot $name
            $hash = Get-FileHash -LiteralPath $path -Algorithm SHA256
            Write-Host "Final asset: $name | $($asset[0].size) bytes | SHA256 $($hash.Hash) | $($asset[0].url)"
        }
    } finally {
        if (Test-Path -LiteralPath $finalRoot) {
            Remove-Item -LiteralPath $finalRoot -Recurse -Force
        }
    }
    return $release
}

function Assert-Tool([string]$Name) {
    if ($null -eq (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command is unavailable: $Name"
    }
}

function Ensure-GitHubAuthentication {
    & $GhCommand auth status *> $null
    if ($LASTEXITCODE -eq 0) {
        return
    }
    $credentialInput = "protocol=https`nhost=github.com`n`n"
    $credentialLines = $credentialInput | git credential fill
    if ($LASTEXITCODE -eq 0) {
        $credentialMap = @{}
        foreach ($line in $credentialLines) {
            $parts = $line -split "=", 2
            if ($parts.Count -eq 2) {
                $credentialMap[$parts[0]] = $parts[1]
            }
        }
        if ($credentialMap.ContainsKey("password") -and $credentialMap["password"]) {
            $env:GH_TOKEN = $credentialMap["password"]
        }
    }
    & $GhCommand auth status *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub authentication is unavailable. Run gh auth login, then retry."
    }
}

try {
    Write-Step "Preflight"
    $versionSource = Get-Content -LiteralPath (Join-Path $projectRoot "version.py") -Raw
    if ($versionSource -notmatch ('(?m)^VERSION = "' + [regex]::Escape($Version) + '"\r?$')) {
        throw "version.py does not match requested version $Version."
    }
    if (-not (Test-Path -LiteralPath $releaseNotes -PathType Leaf)) {
        throw "Missing release notes: $releaseNotes"
    }

    foreach ($tool in @("python", "git")) {
        Assert-Tool $tool
    }
    $systemGh = Get-Command "gh" -ErrorAction SilentlyContinue
    if ($null -ne $systemGh) {
        $GhCommand = $systemGh.Source
    } else {
        $portableGhRoot = Join-Path $projectRoot ".tools\gh"
        $portableGh = Get-ChildItem -LiteralPath $portableGhRoot -Recurse `
            -Filter "gh.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $portableGh) {
            throw "Required command is unavailable: gh. Install GitHub CLI or extract it under .tools\gh."
        }
        $GhCommand = $portableGh.FullName
    }

    $repositoryRoot = (git rev-parse --show-toplevel).Trim()
    if ($LASTEXITCODE -ne 0 -or $repositoryRoot -ne $projectRoot.Replace("\", "/")) {
        throw "Run this script from the Petpet repository."
    }

    $branch = (git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($branch)) {
        throw "A named release branch is required."
    }

    $dirty = git status --porcelain
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect the Git worktree."
    }
    if ($dirty) {
        throw "Release requires a clean worktree."
    }

    Invoke-Native "git" @("fetch", "origin", "main", "--tags")
    & git merge-base --is-ancestor origin/main HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "origin/main is not an ancestor of HEAD; update the release branch without rewriting history."
    }

    $headCommit = (git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to resolve HEAD."
    }

    Write-Step "python -m pytest -q"
    Invoke-Native "python" @("-m", "pytest", "-q")

    Write-Step "python -m py_compile"
    $pythonFiles = @(git ls-files "*.py")
    if ($LASTEXITCODE -ne 0 -or $pythonFiles.Count -eq 0) {
        throw "Unable to enumerate Python source files."
    }
    Invoke-Native "python" (@("-m", "py_compile") + $pythonFiles)

    Write-Step "git diff --check origin/main...HEAD"
    Invoke-Native "git" @("diff", "--check", "origin/main...HEAD")

    Write-Step "Build Windows with build_windows.ps1"
    & (Join-Path $PSScriptRoot "build_windows.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "build_windows.ps1 failed with exit code $LASTEXITCODE."
    }
    if (-not (Test-Path -LiteralPath $exePath -PathType Leaf) -or
        (Get-Item -LiteralPath $exePath).Length -le 0) {
        throw "Windows build did not produce a non-empty Petpet.exe."
    }

    Write-Step "Smoke-test Petpet.exe"
    $smokeProcess = Start-Process -FilePath $exePath `
        -WorkingDirectory (Split-Path -Parent $exePath) `
        -WindowStyle Hidden -PassThru
    try {
        Start-Sleep -Seconds 4
        if ($smokeProcess.HasExited) {
            throw "Petpet.exe exited during the smoke test with code $($smokeProcess.ExitCode)."
        }
    } finally {
        Stop-ProcessTree $smokeProcess.Id
    }

    Write-Step "Package Windows assets"
    New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
    Copy-Item -LiteralPath $exePath -Destination (Join-Path $releaseDir "Petpet.exe") -Force
    if (Test-Path -LiteralPath $windowsZipPath) {
        Remove-Item -LiteralPath $windowsZipPath -Force
    }
    Compress-Archive -LiteralPath $exePath -DestinationPath $windowsZipPath -CompressionLevel Optimal
    $hashLines = @()
    foreach ($path in @($exePath, $windowsZipPath)) {
        $hash = Get-FileHash -LiteralPath $path -Algorithm SHA256
        $hashLines += "$($hash.Hash.ToLowerInvariant())  $([IO.Path]::GetFileName($path))"
    }
    Set-Content -LiteralPath $checksumPath -Value $hashLines -Encoding ASCII

    # Keep GitHub credentials out of pytest/PyInstaller child processes.
    Write-Step "gh auth status"
    Ensure-GitHubAuthentication

    Write-Step "Verify existing release tag before mutation"
    $existingTagCommit = Get-CommandText "git" @("rev-parse", "refs/tags/$Tag^{}")
    if ($existingTagCommit) {
        if ($existingTagCommit -ne $headCommit) {
            throw "Existing release tag does not point to HEAD."
        }
        $tagType = Get-CommandText "git" @("cat-file", "-t", "refs/tags/$Tag")
        if ($tagType -ne "tag") {
            throw "Existing release tag is not annotated."
        }
    }

    $createdLocalTag = $false
    if (-not $existingTagCommit) {
        Write-Step "git tag -a $Tag"
        Invoke-Native "git" @("tag", "-a", $Tag, "-m", "Petpet $Tag")
        $createdLocalTag = $true
    }
    try {
        Write-Step "git push --atomic origin HEAD:main refs/tags/$Tag"
        Invoke-Native "git" @("push", "--atomic", "origin", "HEAD:main", "refs/tags/$Tag")
    } catch {
        if ($createdLocalTag) {
            git tag -d $Tag *> $null
        }
        throw
    }

    Verify-RemoteRefs $headCommit

    $release = Get-ReleaseInfo
    if ($null -eq $release) {
        Write-Step "gh release create --draft"
        Invoke-Native $GhCommand @(
            "release", "create", $Tag, "--draft", "--title", "Pet陪它 $Tag",
            "--notes-file", $releaseNotes, "--target", $headCommit
        )
        $release = Get-ReleaseInfo
    }
    if ($release.tagName -ne $Tag) {
        throw "Existing Release tag does not match $Tag."
    }

    $missingBeforeUpload = @(Get-MissingReleaseAssets)
    if (-not $release.isDraft) {
        if ($missingBeforeUpload.Count -eq 0 -and -not $release.isPrerelease) {
            $verifiedRelease = Verify-PublishedRelease $headCommit
            Write-Host "Release $Tag is already public and complete: $($verifiedRelease.url)"
            exit 0
        }
        throw "Existing public Release is incomplete; refusing to mutate it."
    }

    $existingAssets = Get-ReleaseAssets
    foreach ($path in @($exePath, $windowsZipPath, $checksumPath)) {
        $name = [IO.Path]::GetFileName($path)
        $localSize = (Get-Item -LiteralPath $path).Length
        $remoteAsset = $existingAssets | Where-Object { $_.name -eq $name } | Select-Object -First 1
        if ($null -ne $remoteAsset) {
            if ($remoteAsset.state -ne "uploaded" -or
                [int64]$remoteAsset.size -ne $localSize -or
                -not (Compare-RemoteAssetHash $name $path)) {
                throw "Existing asset content differs from local file: $name"
            }
            Write-Host "Asset already uploaded: $name"
        } else {
            Write-Step "gh release upload $name"
            Invoke-Native $GhCommand @("release", "upload", $Tag, $path)
        }
    }

    $missingMacAssets = @(Get-MissingReleaseAssets | Where-Object { $_ -like "*macOS*" })
    if ($missingMacAssets.Count -gt 0) {
        Verify-RemoteRefs $headCommit
        $dispatchStartedAt = [DateTime]::UtcNow.AddSeconds(-5)
        $dispatchId = [guid]::NewGuid().ToString("N")
        Write-Step "gh workflow run build-macos.yml"
        Invoke-Native $GhCommand @(
            "workflow", "run", "build-macos.yml", "--ref", "main",
            "-f", "release_tag=$Tag", "-f", "dispatch_id=$dispatchId"
        )
        $matchingRun = $null
        for ($attempt = 0; $attempt -lt 30 -and $null -eq $matchingRun; $attempt++) {
            Start-Sleep -Seconds 2
            $runJson = Get-CommandText $GhCommand @(
                "run", "list", "--workflow", "build-macos.yml", "--event",
                "workflow_dispatch", "--limit", "100", "--json",
                "databaseId,displayTitle,headSha,createdAt,event"
            )
            $runs = @($runJson | ConvertFrom-Json)
            $matchingRun = $runs | Where-Object {
                $_.event -eq "workflow_dispatch" -and
                $_.displayTitle -eq "Build macOS $Tag $dispatchId" -and
                $_.headSha -eq $headCommit -and
                [DateTime]::Parse($_.createdAt).ToUniversalTime() -ge $dispatchStartedAt
            } | Sort-Object { [DateTime]::Parse($_.createdAt) } -Descending |
                Select-Object -First 1
        }
        if ($null -eq $matchingRun) {
            throw "Unable to find the dispatched macOS workflow run."
        }
        $runId = [string]$matchingRun.databaseId
        Write-Step "gh run watch $runId"
        Invoke-Native $GhCommand @("run", "watch", $runId, "--exit-status")
    }

    $missingFinal = @(Get-MissingReleaseAssets)
    if ($missingFinal.Count -gt 0) {
        throw "Missing release assets: $($missingFinal -join ', ')"
    }

    Verify-RemoteRefs $headCommit
    Write-Step "gh release edit --draft=false --prerelease=false"
    Invoke-Native $GhCommand @(
        "release", "edit", $Tag, "--draft=false", "--prerelease=false", "--latest"
    )
    $published = Verify-PublishedRelease $headCommit
    Write-Host "Published: $($published.url)" -ForegroundColor Green
} catch {
    Write-Error $_ -ErrorAction Continue
    Write-Host "Re-run: .\scripts\release.ps1 -Version $Version" -ForegroundColor Yellow
    $releaseExitCode = 1
} finally {
    if ($originalGhTokenExists) {
        $env:GH_TOKEN = $originalGhToken
    } else {
        Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue
    }
}
if ($releaseExitCode -ne 0) {
    exit $releaseExitCode
}
