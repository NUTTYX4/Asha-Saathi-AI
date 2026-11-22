<#
.SYNOPSIS
  Point the permanent demo address https://novix-asha-saathi-demo.vercel.app at a Cloudflare tunnel.

.DESCRIPTION
  Writes vercel.json (307 redirects: / -> <tunnel>/v2, /<path> -> <tunnel>/<path>) and deploys it to
  production of the dedicated Vercel project "novix-asha-saathi-demo". The Vercel address never
  changes; only where it sends visitors. Refuses to switch if the tunnel does not answer.
  This project holds no app code and is not connected to Git.

.EXAMPLE
  .\deploy\vercel-redirect\set-demo-link.ps1 https://households-definitions-facilities-comfortable.trycloudflare.com
#>
param(
  [Parameter(Mandatory = $true)][string]$TunnelUrl
)
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$DemoUrl = "https://novix-asha-saathi-demo.vercel.app"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

$TunnelUrl = $TunnelUrl.Trim().TrimEnd("/")
if ($TunnelUrl.EndsWith("/v2")) { $TunnelUrl = $TunnelUrl.Substring(0, $TunnelUrl.Length - 3) }
if ($TunnelUrl -notmatch '^https://[a-z0-9-]+(\.[a-z0-9-]+)+$') {
  throw "Give the tunnel's base address, for example https://abc-def.trycloudflare.com"
}

# Never point the permanent link at a dead tunnel.
try {
  $health = Invoke-RestMethod -Uri "$TunnelUrl/api/health" -TimeoutSec 15
} catch {
  throw "The tunnel did not answer at $TunnelUrl/api/health. Start it first; nothing was changed."
}
if ($health.status -ne "ok") { throw "The tunnel answered but the app is not healthy; nothing was changed." }

$config = [ordered]@{
  '$schema'  = "https://openapi.vercel.sh/vercel.json"
  redirects = @(
    [ordered]@{ source = "/"; destination = "$TunnelUrl/v2"; permanent = $false },
    [ordered]@{ source = "/:path*"; destination = "$TunnelUrl/:path*"; permanent = $false }
  )
}
$json = $config | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText((Join-Path $Here "vercel.json"), $json + "`n", (New-Object System.Text.UTF8Encoding $false))

# Deploy without linking (no .vercel folder, no Git connection prompts).
$env:VERCEL_ORG_ID = "team_1XbzcbfgYJ5IezKhnB6DBCkP"
$env:VERCEL_PROJECT_ID = "prj_Wi989Hu8dBLFHtF2dWNXI3K3NuwA"
Push-Location $Here
try {
  npx --yes vercel@66.6.0 deploy --prod --yes | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "Vercel deploy failed; the previous redirect is still live." }
} finally {
  Pop-Location
  Remove-Item Env:VERCEL_ORG_ID, Env:VERCEL_PROJECT_ID -ErrorAction SilentlyContinue
}

# Confirm the permanent address now sends visitors to the tunnel.
$request = [System.Net.HttpWebRequest]::Create("$DemoUrl/")
$request.AllowAutoRedirect = $false
$raw = $request.GetResponse()
$location = $raw.Headers["Location"]
$code = [int]$raw.StatusCode
$raw.Close()
Write-Host ""
Write-Host "$DemoUrl  ->  $code $location"
if ($location -ne "$TunnelUrl/v2") { Write-Warning "Redirect not updated yet; run the script again in a minute." }
