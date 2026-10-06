param(
    [ValidateRange(1, 65535)][int]$Port = 8000,
    [ValidateSet("auto", "http2", "quic")][string]$Protocol = "auto",
    [string]$CloudflaredPath = "cloudflared"
)
$ErrorActionPreference = "Stop"
$command = Get-Command $CloudflaredPath -ErrorAction SilentlyContinue
if (-not $command) {
    throw "Install cloudflared, or pass -CloudflaredPath with its executable path."
}
$origin = "http://127.0.0.1:$Port"
# Host rewrite lets Vite keep its default host allow-list for frontend previews.
$process = Start-Process -FilePath $command.Source -NoNewWindow -Wait -PassThru -ArgumentList @(
    "tunnel", "--url", $origin, "--http-host-header", "localhost:$Port", "--protocol", $Protocol
)
exit $process.ExitCode
