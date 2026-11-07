# Stops all USBPcapCMD captures (run elevated).
$log = 'C:\Users\lance\OneDrive\Documents\_CODE\8bitdo\captures\stop.log'
"stop $(Get-Date -Format o)" | Out-File $log
Get-Process USBPcapCMD -ErrorAction SilentlyContinue | ForEach-Object { "killing pid=$($_.Id)" | Out-File $log -Append; Stop-Process -Id $_.Id -Force -Confirm:$false }
