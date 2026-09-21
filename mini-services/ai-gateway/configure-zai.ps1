$ErrorActionPreference = 'Stop'

$configPath = Join-Path $PSScriptRoot '.z-ai-config'
$secureKey = Read-Host 'Cole sua Z.AI API Key (entrada oculta)' -AsSecureString
$apiKey = [System.Net.NetworkCredential]::new('', $secureKey).Password

if ([string]::IsNullOrWhiteSpace($apiKey)) {
  throw 'Nenhuma chave foi informada. Nenhum arquivo foi alterado.'
}

$config = [ordered]@{
  baseUrl = 'https://api.z.ai/api/paas/v4'
  apiKey  = $apiKey.Trim()
} | ConvertTo-Json

Set-Content -LiteralPath $configPath -Value $config -Encoding utf8 -NoNewline
Write-Host 'Configuração local salva. Volte ao chat e diga: foi.' -ForegroundColor Green
