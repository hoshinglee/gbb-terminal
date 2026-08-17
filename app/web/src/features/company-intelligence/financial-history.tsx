import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { CompanyMetric, CompanyMetricsResponse } from "@/lib/types"
import { cn } from "@/lib/utils"

export type FinancialPeriodKind = "annual" | "quarterly" | "ttm"

export type FinancialMetricSets = Record<FinancialPeriodKind, CompanyMetricsResponse | null>

const metricIds = [
  "revenue",
  "revenue_growth",
  "net_income",
  "diluted_eps",
  "gross_margin",
  "operating_margin",
  "free_cash_flow",
  "return_on_invested_capital",
]

const periodPresentation: Array<{ kind: FinancialPeriodKind; title: string; description: string }> = [
  { kind: "ttm", title: "Trailing Twelve Months", description: "Rolling four-quarter evidence. Each row uses only quarters available by the as-of boundary." },
  { kind: "quarterly", title: "Quarterly History", description: "Discrete fiscal-quarter evidence, including issuer-reported and deterministically inferred fourth quarters." },
  { kind: "annual", title: "Annual History", description: "Full-year normalized history remains available independently of price or valuation chart windows." },
]

function compact(value: number) {
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(value)
}

function metricValue(metric?: CompanyMetric) {
  if (!metric || metric.value === null) return "—"
  if (metric.unit === "USD") return `$${compact(metric.value)}`
  if (metric.unit === "USD/share") return `$${metric.value.toFixed(2)}`
  if (metric.unit === "%") return `${metric.value.toFixed(2)}%`
  if (metric.unit === "shares") return compact(metric.value)
  return metric.value.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function periods(metrics: CompanyMetric[]) {
  return [...new Set(metrics.map((metric) => metric.periodEnd))].sort().reverse()
}

function periodMetric(metrics: CompanyMetric[], metricId: string, periodEnd: string) {
  return metrics.find((metric) => metric.metricId === metricId && metric.periodEnd === periodEnd)
}

function metricLabel(metrics: CompanyMetric[], metricId: string) {
  return metrics.find((metric) => metric.metricId === metricId)?.label || metricId.replaceAll("_", " ")
}

function periodLabel(periodEnd: string, metrics: CompanyMetric[]) {
  const representative = metrics.find((metric) => metric.periodEnd === periodEnd)
  if (!representative) return periodEnd
  const fiscal = [representative.fiscalPeriod, representative.fiscalYear].filter(Boolean).join(" ")
  return fiscal ? `${fiscal} · ${periodEnd}` : periodEnd
}

function comparison(current?: CompanyMetric, previous?: CompanyMetric) {
  if (current?.value === null || current?.value === undefined || previous?.value === null || previous?.value === undefined) return null
  const change = current.value - previous.value
  if (Math.abs(change) < 1e-12) return { direction: "flat" as const, label: "Unchanged vs prior" }
  if (current.unit === "%") {
    return { direction: change > 0 ? "up" as const : "down" as const, label: `${Math.abs(change).toFixed(2)} pp vs prior` }
  }
  if (previous.value === 0) return { direction: change > 0 ? "up" as const : "down" as const, label: "Changed vs prior" }
  const percent = Math.abs((change / Math.abs(previous.value)) * 100)
  return { direction: change > 0 ? "up" as const : "down" as const, label: `${percent.toFixed(1)}% vs prior` }
}

function MetricCell({ current, previous }: { current?: CompanyMetric; previous?: CompanyMetric }) {
  const context = comparison(current, previous)
  return <div className="min-w-24"><span className="font-medium text-foreground">{metricValue(current)}</span>{context ? <span className={cn("mt-1 flex items-center gap-1 text-[9px]", context.direction === "up" ? "text-primary" : context.direction === "down" ? "text-destructive" : "text-muted-foreground")}>{context.direction === "up" ? <ArrowUpRight className="size-3" /> : context.direction === "down" ? <ArrowDownRight className="size-3" /> : <Minus className="size-3" />}{context.label}</span> : <span className="mt-1 block text-[9px] text-muted-foreground">No comparable prior period</span>}</div>
}

function FinancialPeriodTable({ response, title, description }: { response: CompanyMetricsResponse | null; title: string; description: string }) {
  const metrics = response?.metrics || []
  const availablePeriods = periods(metrics)
  return <Card className="gap-0 overflow-hidden py-0">
    <CardHeader className="border-b py-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>{title}</CardTitle><CardDescription className="mt-2 max-w-3xl">{description}</CardDescription></div><Badge variant="outline">{availablePeriods.length} periods · all available</Badge></div></CardHeader>
    {availablePeriods.length ? <div className="max-h-[560px] overflow-auto"><Table><TableHeader className="sticky top-0 z-10 bg-card"><TableRow><TableHead>Fiscal Period</TableHead>{metricIds.map((metricId) => <TableHead key={metricId}>{metricLabel(metrics, metricId)}</TableHead>)}</TableRow></TableHeader><TableBody>{availablePeriods.map((periodEnd, index) => {
      const previousPeriod = availablePeriods[index + 1]
      return <TableRow key={periodEnd}><TableCell className="whitespace-nowrap font-mono text-xs">{periodLabel(periodEnd, metrics)}</TableCell>{metricIds.map((metricId) => <TableCell key={metricId}><MetricCell current={periodMetric(metrics, metricId, periodEnd)} previous={previousPeriod ? periodMetric(metrics, metricId, previousPeriod) : undefined} /></TableCell>)}</TableRow>
    })}</TableBody></Table></div> : <CardContent className="grid min-h-40 place-items-center text-center text-sm text-muted-foreground">No normalized {response?.periodKind || "financial"} periods are available inside the current as-of boundary.</CardContent>}
    {response?.warnings.length ? <div className="border-t px-5 py-3 text-xs leading-5 text-muted-foreground">{response.warnings.join(" ")}</div> : null}
  </Card>
}

export function FinancialHistory({ datasets }: { datasets: FinancialMetricSets }) {
  return <div className="space-y-4">
    <Card><CardHeader><CardTitle>Complete Normalized Financial History</CardTitle><CardDescription>Annual, quarterly, and TTM clocks are intentionally independent from earnings-event, market-price, and valuation windows. Primary figures stay neutral; arrows describe only comparable period movement.</CardDescription></CardHeader><CardContent className="grid gap-3 sm:grid-cols-3">{periodPresentation.map(({ kind, title }) => <div key={kind} className="rounded-lg border bg-background/45 p-4"><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">{title}</span><strong className="mt-2 block text-2xl">{periods(datasets[kind]?.metrics || []).length}</strong><small className="mt-1 block text-muted-foreground">available periods</small></div>)}</CardContent></Card>
    {periodPresentation.map(({ kind, title, description }) => <FinancialPeriodTable key={kind} response={datasets[kind]} title={title} description={description} />)}
  </div>
}
