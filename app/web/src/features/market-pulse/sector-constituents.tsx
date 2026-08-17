import { AlertCircle, Database, Grid3X3, List, TrendingDown, TrendingUp } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { labHref } from "@/lib/navigation"
import type { SectorConstituentResearch, SectorConstituentSnapshot } from "@/lib/types"

interface Bounds {
  x: number
  y: number
  width: number
  height: number
}

export interface TreemapRectangle extends Bounds {
  item: SectorConstituentResearch
  usesEqualAreaFallback: boolean
}

function balancedIndex(values: number[]) {
  const target = values.reduce((sum, value) => sum + value, 0) / 2
  let running = 0
  let bestIndex = 1
  let bestDistance = Number.POSITIVE_INFINITY
  for (let index = 1; index < values.length; index += 1) {
    running += values[index - 1]
    const distance = Math.abs(target - running)
    if (distance < bestDistance) {
      bestDistance = distance
      bestIndex = index
    }
  }
  return bestIndex
}

function partition(
  items: SectorConstituentResearch[],
  values: number[],
  bounds: Bounds,
  fallback: boolean,
): TreemapRectangle[] {
  if (items.length === 0) return []
  if (items.length === 1) return [{ ...bounds, item: items[0], usesEqualAreaFallback: fallback }]
  const splitAt = balancedIndex(values)
  const firstValues = values.slice(0, splitAt)
  const secondValues = values.slice(splitAt)
  const firstTotal = firstValues.reduce((sum, value) => sum + value, 0)
  const total = firstTotal + secondValues.reduce((sum, value) => sum + value, 0)
  const ratio = total > 0 ? firstTotal / total : splitAt / items.length
  const horizontal = bounds.width >= bounds.height
  const firstBounds = horizontal
    ? { ...bounds, width: bounds.width * ratio }
    : { ...bounds, height: bounds.height * ratio }
  const secondBounds = horizontal
    ? { x: bounds.x + firstBounds.width, y: bounds.y, width: bounds.width - firstBounds.width, height: bounds.height }
    : { x: bounds.x, y: bounds.y + firstBounds.height, width: bounds.width, height: bounds.height - firstBounds.height }
  return [
    ...partition(items.slice(0, splitAt), firstValues, firstBounds, fallback),
    ...partition(items.slice(splitAt), secondValues, secondBounds, fallback),
  ]
}

export function buildTreemapLayout(
  constituents: SectorConstituentResearch[],
  width = 1000,
  height = 460,
): TreemapRectangle[] {
  const known = constituents
    .filter((item) => item.marketCap !== null && item.marketCap > 0)
    .sort((left, right) => (right.marketCap || 0) - (left.marketCap || 0))
  const missing = constituents.filter((item) => item.marketCap === null || item.marketCap <= 0)
  if (!known.length) {
    return partition(missing, missing.map(() => 1), { x: 0, y: 0, width, height }, true)
  }
  if (!missing.length) {
    return partition(known, known.map((item) => item.marketCap || 1), { x: 0, y: 0, width, height }, false)
  }
  const fallbackHeight = Math.min(height * 0.28, Math.max(height * 0.16, missing.length * 5))
  return [
    ...partition(
      known,
      known.map((item) => item.marketCap || 1),
      { x: 0, y: 0, width, height: height - fallbackHeight },
      false,
    ),
    ...partition(
      missing,
      missing.map(() => 1),
      { x: 0, y: height - fallbackHeight, width, height: fallbackHeight },
      true,
    ),
  ]
}

function movementColor(change: number | null) {
  if (change === null) return "hsl(155 10% 24%)"
  const intensity = Math.min(Math.abs(change) / 5, 1)
  if (change > 0) return `hsl(86 58% ${22 + intensity * 17}%)`
  if (change < 0) return `hsl(0 58% ${22 + intensity * 17}%)`
  return "hsl(155 12% 28%)"
}

function money(value: number | null) {
  if (value === null) return "Unavailable"
  if (value >= 1_000_000_000_000) return `$${(value / 1_000_000_000_000).toFixed(2)}T`
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`
  return `$${(value / 1_000_000).toFixed(1)}M`
}

function signedPercent(value: number | null) {
  return value === null ? "Unavailable" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

function SectorTreemap({ data }: { data: SectorConstituentSnapshot }) {
  const rectangles = buildTreemapLayout(data.constituents)
  return <figure>
    <svg viewBox="0 0 1000 460" className="min-h-80 w-full rounded-lg border bg-background/60" role="img" aria-labelledby="sector-treemap-title sector-treemap-description">
      <title id="sector-treemap-title">{data.sectorName} constituent market map</title>
      <desc id="sector-treemap-description">Known market capitalizations determine rectangle area. Dashed rectangles use equal area because market capitalization is unavailable. Color reflects the latest daily move.</desc>
      {rectangles.map((rectangle) => {
        const showName = rectangle.width >= 72 && rectangle.height >= 36
        const showDetail = rectangle.width >= 105 && rectangle.height >= 58
        const label = `${rectangle.item.symbol}, ${rectangle.item.companyName}, daily move ${signedPercent(rectangle.item.dailyChangePercent)}, market capitalization ${money(rectangle.item.marketCap)}${rectangle.usesEqualAreaFallback ? ", equal-area fallback" : ""}`
        return <a key={rectangle.item.symbol} href={labHref("intelligence", rectangle.item.symbol)} aria-label={`Open Company Intelligence for ${label}`}>
          <g>
            <title>{label}</title>
            <rect
              x={rectangle.x + 1}
              y={rectangle.y + 1}
              width={Math.max(rectangle.width - 2, 0)}
              height={Math.max(rectangle.height - 2, 0)}
              rx="4"
              fill={movementColor(rectangle.item.dailyChangePercent)}
              stroke={rectangle.usesEqualAreaFallback ? "#b7c5bd" : "#07100d"}
              strokeDasharray={rectangle.usesEqualAreaFallback ? "5 4" : undefined}
              strokeWidth="2"
            />
            {showName ? <text x={rectangle.x + 9} y={rectangle.y + 20} fill="#f2f7f4" fontSize="13" fontWeight="700">{rectangle.item.symbol}</text> : null}
            {showDetail ? <text x={rectangle.x + 9} y={rectangle.y + 39} fill="#e0ebe5" fontSize="10">{signedPercent(rectangle.item.dailyChangePercent)}</text> : null}
            {showDetail && rectangle.usesEqualAreaFallback ? <text x={rectangle.x + 9} y={rectangle.y + 54} fill="#c0cec6" fontSize="8">CAP N/A · EQUAL AREA</text> : null}
          </g>
        </a>
      })}
    </svg>
    <figcaption className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10px] text-muted-foreground">
      <span><Grid3X3 className="mr-1 inline size-3" />Area = calculated point-in-time market cap · green/red = latest daily move</span>
      <span>Dashed = equal-area fallback when market cap is unavailable</span>
    </figcaption>
  </figure>
}

function RankingTable({ title, rows, direction }: { title: string; rows: SectorConstituentResearch[]; direction: "up" | "down" }) {
  const Icon = direction === "up" ? TrendingUp : TrendingDown
  return <Card className="gap-0 overflow-hidden"><CardHeader className="border-b"><div className="flex items-center gap-2"><Icon className={direction === "up" ? "size-4 text-primary" : "size-4 text-destructive"} /><CardTitle className="text-base">{title}</CardTitle></div><CardDescription>Ranked by the latest cached daily percentage move, not by expected return.</CardDescription></CardHeader><CardContent className="px-0"><Table><TableHeader><TableRow><TableHead>Company</TableHead><TableHead>Day</TableHead><TableHead>Price</TableHead><TableHead>Market Cap</TableHead></TableRow></TableHeader><TableBody>{rows.length ? rows.map((item) => <TableRow key={item.symbol}><TableCell><a className="font-semibold hover:text-primary hover:underline" href={labHref("intelligence", item.symbol)}>{item.symbol}</a><small className="ml-2 text-muted-foreground">{item.companyName}</small></TableCell><TableCell className={direction === "up" ? "text-primary" : "text-destructive"}>{signedPercent(item.dailyChangePercent)}</TableCell><TableCell>{item.price === null ? "—" : `$${item.price.toFixed(2)}`}</TableCell><TableCell>{money(item.marketCap)}</TableCell></TableRow>) : <TableRow><TableCell colSpan={4} className="h-20 text-center text-muted-foreground">No qualifying cached rows.</TableCell></TableRow>}</TableBody></Table></CardContent></Card>
}

function AllConstituents({ data }: { data: SectorConstituentSnapshot }) {
  return <details className="rounded-lg border bg-background/35"><summary className="cursor-pointer px-4 py-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"><List className="mr-2 inline size-4" />Accessible constituent list ({data.constituentCount})</summary><div className="border-t"><Table><TableCaption>All current-snapshot constituents remain listed, including companies with unavailable cached research.</TableCaption><TableHeader><TableRow><TableHead>Company</TableHead><TableHead>Industry</TableHead><TableHead>Day</TableHead><TableHead>Market Cap</TableHead><TableHead>Observed</TableHead><TableHead>Cache</TableHead></TableRow></TableHeader><TableBody>{data.constituents.map((item) => <TableRow key={item.symbol}><TableCell><Button asChild size="xs" variant="ghost"><a href={labHref("intelligence", item.symbol)}>{item.symbol}</a></Button><small className="ml-2 text-muted-foreground">{item.companyName}</small></TableCell><TableCell>{item.subIndustry}</TableCell><TableCell>{signedPercent(item.dailyChangePercent)}</TableCell><TableCell>{money(item.marketCap)}{item.marketCap === null ? <small className="ml-2 text-muted-foreground">Equal-area fallback</small> : null}</TableCell><TableCell>{item.observationTimestamp ? new Date(item.observationTimestamp).toLocaleDateString() : "Not Cached"}</TableCell><TableCell><Badge variant={item.dataStatus === "completed" ? "outline" : item.dataStatus === "partial" ? "secondary" : "destructive"}>{item.dataStatus.replaceAll("_", " ")}</Badge></TableCell></TableRow>)}</TableBody></Table></div></details>
}

export function SectorConstituents({ data, loading, error, onRetry }: { data: SectorConstituentSnapshot | null; loading: boolean; error: string; onRetry: () => void }) {
  if (loading) return <Card><CardContent className="grid min-h-52 place-items-center text-sm text-muted-foreground">Loading the local constituent research cache…</CardContent></Card>
  if (error) return <Alert variant="destructive"><AlertCircle /><AlertTitle>Sector Constituents Unavailable</AlertTitle><AlertDescription className="flex flex-wrap items-center justify-between gap-3"><span>{error}</span><Button size="sm" variant="outline" onClick={onRetry}>Try Again</Button></AlertDescription></Alert>
  if (!data) return null
  return <section aria-labelledby="sector-constituents-title" className="space-y-4">
    <Card className="gap-4"><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="mb-2 flex items-center gap-2"><Database className="size-4 text-primary" /><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-primary">Local S&amp;P 500 Research Cache</span></div><CardTitle id="sector-constituents-title">{data.sectorName} Constituents</CardTitle><CardDescription className="mt-2">{data.availableCount} of {data.constituentCount} current-snapshot members have a cached daily move. Select a company to continue in Company Intelligence.</CardDescription></div><Badge variant="outline">{data.sectorSymbol} · Snapshot {data.snapshotId.slice(0, 8)}</Badge></div></CardHeader><CardContent className="space-y-4 border-t pt-5"><SectorTreemap data={data} />{data.warnings.length ? <Alert><AlertCircle /><AlertTitle>Universe Context</AlertTitle><AlertDescription>{data.warnings.join(" ")}</AlertDescription></Alert> : null}<AllConstituents data={data} /></CardContent></Card>
    <div className="grid gap-4 2xl:grid-cols-2"><RankingTable title="Top Daily Gainers" rows={data.gainers} direction="up" /><RankingTable title="Top Daily Losers" rows={data.losers} direction="down" /></div>
  </section>
}
