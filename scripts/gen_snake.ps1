param(
  [double]$DurSeconds = 18.0,
  [string]$InputSvg = "assets/whoismrsentry_snake_carve.svg",
  [string]$OutX = "assets/_gen_snake_x.txt",
  [string]$OutY = "assets/_gen_snake_y.txt",
  [string]$OutFill = "assets/_gen_snake_fill.txt",
  [string]$OutCarve = "assets/_gen_carve_rects.txt"
)

$dt = $DurSeconds / 365.0
$content = Get-Content -Raw -LiteralPath $InputSvg

$inv = [System.Globalization.CultureInfo]::InvariantCulture

$rx = [regex]'<rect class="cell green" x="(?<x>\d+)" y="(?<y>\d+)"'
$m = $rx.Matches($content)

$targets = @{}
foreach ($mm in $m) {
  $key = "$($mm.Groups['x'].Value),$($mm.Groups['y'].Value)"
  $targets[$key] = $true
}

function StepIndex([int]$x, [int]$y) {
  $col = [int](($x - 14) / 18)
  $row = [int](($y - 34) / 18)
  if ($col % 2 -eq 0) {
    return $col * 7 + $row
  }
  return $col * 7 + (6 - $row)
}

$xArr = New-Object System.Collections.Generic.List[string]
$yArr = New-Object System.Collections.Generic.List[string]
$fillArr = New-Object System.Collections.Generic.List[string]

for ($col = 0; $col -le 52; $col++) {
  $x = 14 + 18 * $col

  if ($col -eq 52) {
    $y = 34
    $xArr.Add([string]$x)
    $yArr.Add([string]$y)
    $key = "$x,$y"
    $fillArr.Add($(if ($targets.ContainsKey($key)) { '#39ff14' } else { '#88001b' }))
    continue
  }

  if ($col % 2 -eq 0) {
    for ($row = 0; $row -le 6; $row++) {
      $y = 34 + 18 * $row
      $xArr.Add([string]$x)
      $yArr.Add([string]$y)
      $key = "$x,$y"
      $fillArr.Add($(if ($targets.ContainsKey($key)) { '#39ff14' } else { '#88001b' }))
    }
  } else {
    for ($row = 6; $row -ge 0; $row--) {
      $y = 34 + 18 * $row
      $xArr.Add([string]$x)
      $yArr.Add([string]$y)
      $key = "$x,$y"
      $fillArr.Add($(if ($targets.ContainsKey($key)) { '#39ff14' } else { '#88001b' }))
    }
  }
}

if ($xArr.Count -ne 365) {
  throw "Expected 365 steps, got $($xArr.Count)"
}

$carveLines = New-Object System.Collections.Generic.List[string]
foreach ($mm in $m) {
  $x = [int]$mm.Groups['x'].Value
  $y = [int]$mm.Groups['y'].Value

  $idx = StepIndex $x $y
  $ratio = ($idx * $dt) / $DurSeconds
  if ($ratio -lt 0) { $ratio = 0 }
  if ($ratio -gt 1) { $ratio = 1 }
  $ratioStr = ([math]::Round($ratio, 5)).ToString('0.#####', $inv)
  $durStr = $DurSeconds.ToString('0.#####', $inv)

  $carveLines.Add(
    "    <rect class=""cell hole"" x=""$x"" y=""$y"" width=""15"" height=""15"" rx=""3""><animate attributeName=""fill"" calcMode=""discrete"" dur=""${durStr}s"" repeatCount=""indefinite"" values=""#200009;#39ff14;#39ff14"" keyTimes=""0;${ratioStr};1"" /></rect>"
  )
}

Set-Content -LiteralPath $OutX -Value ($xArr -join ';') -NoNewline
Set-Content -LiteralPath $OutY -Value ($yArr -join ';') -NoNewline
Set-Content -LiteralPath $OutFill -Value ($fillArr -join ';') -NoNewline
Set-Content -LiteralPath $OutCarve -Value ($carveLines -join "`n") -NoNewline

Write-Output "OK steps=$($xArr.Count) targets=$($m.Count) dur=$DurSeconds"