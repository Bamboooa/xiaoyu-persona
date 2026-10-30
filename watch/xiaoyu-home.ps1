# Xiaoyu Home Dashboard launcher
$RPORT = 18088
$LHOST = 8088
$SRV   = "ubuntu@49.233.141.211"

function Test-Port {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $ok = $c.ConnectAsync('127.0.0.1', $RPORT).Wait(800)
        $c.Close()
        return $ok
    } catch { return $false }
}

if (-not (Test-Port)) {
    $a = @(
        "-N",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=NUL",
        "-o", "ServerAliveInterval=30",
        "-o", "ExitOnForwardFailure=yes",
        "-L", "$($RPORT):127.0.0.1:$LHOST",
        $SRV
    )
    Start-Process ssh -ArgumentList $a -WindowStyle Hidden
    $ready = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Milliseconds 800
        if (Test-Port) { $ready = $true; break }
    }
    if (-not $ready) {
        Write-Host "Tunnel failed. Check network or server."
        Start-Sleep -Seconds 4
        exit 1
    }
}

Start-Process "http://127.0.0.1:$RPORT/"