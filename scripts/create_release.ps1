param(
    [switch]$SkipBuild,
    [string]$SpecPath = "DiscordEmotify.spec",
    [string]$CertificateThumbprint,
    [string]$PfxPath,
    [string]$PfxPassword,
    [string]$TimestampUrl = "http://timestamp.digicert.com",
    [string]$PyInstaller = "pyinstaller"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptDir "..")
Push-Location $projectRoot

try {
    if (-not $SkipBuild.IsPresent) {
        if (-not (Get-Command $PyInstaller -ErrorAction SilentlyContinue)) {
            throw "PyInstaller ($PyInstaller) is not available on PATH. Install it with 'pip install pyinstaller'."
        }
        & $PyInstaller --clean --noconfirm $SpecPath
    }

    $exePath = Join-Path $projectRoot "dist\DiscordEmotify\DiscordEmotify.exe"
    if (-not (Test-Path $exePath)) {
        throw "Executable not found at '$exePath'. Ensure the build step succeeded."
    }

    $certificate = $null
    if ($PfxPath) {
        if (-not (Test-Path $PfxPath)) {
            throw "PFX certificate not found at '$PfxPath'."
        }
        if (-not $PfxPassword) {
            throw "Provide -PfxPassword for the supplied PFX certificate."
        }
        $securePassword = ConvertTo-SecureString $PfxPassword -AsPlainText -Force
        $imported = Import-PfxCertificate -FilePath $PfxPath -Password $securePassword -CertStoreLocation Cert:\CurrentUser\My
        if (-not $imported) {
            throw "Failed to import PFX certificate."
        }
        $certificate = $imported | Select-Object -First 1
        Write-Host "Imported certificate '$($certificate.Subject)' (Thumbprint: $($certificate.Thumbprint))."
    } elseif ($CertificateThumbprint) {
        $trimThumb = $CertificateThumbprint.Replace(" ", "")
        $certificate = Get-ChildItem -Path "Cert:\CurrentUser\My\$trimThumb" -ErrorAction SilentlyContinue
        if (-not $certificate) {
            throw "No certificate found in CurrentUser\My with thumbprint '$CertificateThumbprint'."
        }
    }

    if ($certificate) {
        Write-Host "Signing $exePath ..."
        Set-AuthenticodeSignature -FilePath $exePath -Certificate $certificate -TimestampServer $TimestampUrl | Out-Null
        Write-Host "Signature applied with certificate: $($certificate.Subject)."
    } else {
        Write-Warning "No certificate provided. The executable will remain unsigned."
    }

    $distDir = Join-Path $projectRoot "dist"
    if (-not (Test-Path $distDir)) {
        throw "Expected dist directory at '$distDir'."
    }

    $versionMatch = Select-String -Path (Join-Path $projectRoot "DiscordEmotify.py") -Pattern '__version__\s*=\s*"([^"]+)"'
    if (-not $versionMatch) {
        throw "Unable to determine application version from DiscordEmotify.py."
    }
    $version = $versionMatch.Matches[0].Groups[1].Value

    $zipName = "DiscordEmotify-v$version-win64.zip"
    $zipPath = Join-Path $distDir $zipName
    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }

    $sourcePattern = Join-Path $distDir "DiscordEmotify\*"
    Compress-Archive -Path $sourcePattern -DestinationPath $zipPath -Force
    Write-Host "Created archive: $zipPath"

    $hash = Get-FileHash -Algorithm SHA256 -Path $zipPath
    $hashLine = "{0} *{1}" -f $hash.Hash, (Split-Path $zipPath -Leaf)
    $hashFile = "$zipPath.sha256"
    $hashLine | Set-Content -Path $hashFile -Encoding ASCII
    Write-Host "SHA256: $hashLine"
    Write-Host "Checksum file written to $hashFile"

    if ($certificate) {
        $sigStatus = Get-AuthenticodeSignature -FilePath $exePath
        Write-Host "Signature status: $($sigStatus.Status)"
    }
}
finally {
    Pop-Location
}
