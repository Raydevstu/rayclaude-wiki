$event = [Console]::In.ReadToEnd() | ConvertFrom-Json
$text = if ($event.content) { [string]$event.content } elseif ($event.prompt) { [string]$event.prompt } elseif ($event.response) { [string]$event.response } else { return }
if ([string]::IsNullOrWhiteSpace($text)) { return }
try { & python -m tier1 memory add $text | Out-Null } catch { }
