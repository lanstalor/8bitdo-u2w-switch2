# Starts USBPcapCMD on both root hubs (run elevated). Usage: cap_start.ps1 <tag>
param([Parameter(Mandatory=$true)][string]$Tag)
$ErrorActionPreference = 'Stop'
$dir = 'C:\Users\lance\OneDrive\Documents\_CODE\8bitdo\captures'
New-Item -ItemType Directory -Force $dir | Out-Null
$exe = 'C:\Program Files\USBPcap\USBPcapCMD.exe'
$log = Join-Path $dir "$Tag.log"
"start $(Get-Date -Format o)" | Out-File $log
foreach ($n in 1, 2) {
    $out = Join-Path $dir "$Tag-usbpcap$n.pcap"
    $p = Start-Process -FilePath $exe -ArgumentList @('-d', "\\.\USBPcap$n", '-o', "`"$out`"", '-A', '--inject-descriptors', '-b', '16777216') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $dir "$Tag-usbpcap$n.stdout.txt") -RedirectStandardError (Join-Path $dir "$Tag-usbpcap$n.stderr.txt")
    "USBPcap$n pid=$($p.Id) -> $out" | Out-File $log -Append
}
Start-Sleep -Seconds 2
Get-Process USBPcapCMD -ErrorAction SilentlyContinue | ForEach-Object { "running pid=$($_.Id)" } | Out-File $log -Append
