import { AlertTriangle, ChartNoAxesColumnIncreasing, Gauge, Globe2, Layers3 } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { SourceEvidenceDialog } from "@/features/company-intelligence/source-evidence-dialog"
import type {
  OperatingIntelligenceResponse,
  OperatingMetricCategory,
  OperatingMetricPoint,
  OperatingMetricSeries,
} from "@/lib/types"

const categoryLabels: Record<OperatingMetricCategory, string> = {
  segment: "Business Segments",
  geography: "Geographic Mix",
  kpi: "Company KPIs",
}

function readableDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function compact(value: number) {
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(value)
}

function metricValue(value: number, unit: string, valueType: OperatingMetricSeries["definition"]["valueType"]) {
  const normalizedUnit = unit.toLowerCase()
  if (normalizedUnit === "usd millions") return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}M`
  if (normalizedUnit === "usd billions") return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}B`
  if (normalizedUnit === "usd thousands") return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}K`
  if (valueType === "currency" || unit === "USD") return `$${compact(value)}`
  if (valueType === "percentage" || unit === "%") return `${value.toFixed(2)}%`
  if (valueType === "ratio") return `${value.toFixed(2)}×`
  if (valueType === "count") return compact(value)
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit}`
}

function percentage(value: number | null) {
  return value === null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

function latestPoint(series: OperatingMetricSeries) {
  return series.points.at(-1)
}

function CategoryIcon({ category }: { category: OperatingMetricCategory }) {
  if (category === "segment") return <Layers3 className="size-4 text-primary" />
  if (category === "geography") return <Globe2 className="size-4 text-chart-2" />
  return <Gauge className="size-4 text-chart-3" />
}

function MixCard({ series }: { series: OperatingMetricSeries }) {
  const point = latestPoint(series)
  if (!point) return null
  const width = Math.max(0, Math.min(point.mixPercent || 0, 100))
  return <article className="rounded-lg border bg-background/45 p-4">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div>
        <strong className="block text-sm">{series.definition.label}</strong>
        <span className="mt-1 block text-[10px] text-muted-foreground">{series.definition.reportingBasis} · Version {series.definition.version}</span>
      </div>
      <div className="flex flex-wrap gap-2"><SourceEvidenceDialog evidence={series.definitionEvidence} label="Definition" title={`${series.definition.label} definition evidence`} /><SourceEvidenceDialog evidence={point.evidence} label="Value" title={`${series.definition.label} operating evidence`} /></div>
    </div>
    <div className="mt-4 flex items-end justify-between gap-3">
      <strong className="text-xl">{metricValue(point.observation.value, point.observation.unit, series.definition.valueType)}</strong>
      <span className="font-mono text-xs text-muted-foreground">{readableDate(point.observation.periodEnd)}</span>
    </div>
    <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted" aria-label={`${series.definition.label} mix ${point.mixPercent === null ? "unavailable" : `${point.mixPercent.toFixed(2)} percent`}`}>
      <div className="h-full rounded-full bg-primary" style={{ width: `${width}%` }} />
    </div>
    <div className="mt-2 flex justify-between text-[10px] text-muted-foreground">
      <span>{point.mixPercent === null ? "Mix unavailable" : `${point.mixPercent.toFixed(2)}% of compatible disclosed total`}</span>
      <span>{point.growthPercent === null ? "No compatible prior period" : `${percentage(point.growthPercent)} growth`}</span>
    </div>
  </article>
}

function EvidenceTable({ series }: { series: OperatingMetricSeries[] }) {
  const rows = series.flatMap((item) => item.points.map((point) => ({ series: item, point })))
  if (!rows.length) return null
  return <div className="overflow-x-auto rounded-lg border">
    <Table>
      <TableHeader><TableRow><TableHead>Metric</TableHead><TableHead>Period</TableHead><TableHead>Reported Value</TableHead><TableHead>Mix</TableHead><TableHead>Growth</TableHead><TableHead>Definition</TableHead><TableHead>Known At</TableHead><TableHead>Evidence</TableHead></TableRow></TableHeader>
      <TableBody>{rows.sort((left, right) => right.point.observation.periodEnd.localeCompare(left.point.observation.periodEnd)).map(({ series: item, point }) => <TableRow key={point.observation.observationId}>
        <TableCell><strong className="block min-w-36">{item.definition.label}</strong><span className="text-[10px] text-muted-foreground">{item.definition.measure}</span></TableCell>
        <TableCell className="font-mono text-[10px]">{point.observation.fiscalPeriod || "Period"} {point.observation.fiscalYear || ""}<span className="block text-muted-foreground">{point.observation.periodEnd}</span></TableCell>
        <TableCell>{metricValue(point.observation.value, point.observation.unit, item.definition.valueType)}</TableCell>
        <TableCell>{percentage(point.mixPercent)}</TableCell>
        <TableCell>{percentage(point.growthPercent)}</TableCell>
        <TableCell><Badge variant="outline">v{item.definition.version}</Badge><span className="mt-1 block min-w-36 text-[10px] text-muted-foreground">{item.definition.reportingBasis}</span></TableCell>
        <TableCell className="font-mono text-[10px]">{new Date(point.observation.knownAt).toLocaleString()}</TableCell>
        <TableCell><div className="flex flex-wrap gap-2"><SourceEvidenceDialog evidence={item.definitionEvidence} label="Definition" title={`${item.definition.label} definition evidence`} /><SourceEvidenceDialog evidence={point.evidence} label="Value" title={`${item.definition.label} observation evidence`} /></div></TableCell>
      </TableRow>)}</TableBody>
    </Table>
  </div>
}

function OperatingSection({ category, series }: { category: OperatingMetricCategory; series: OperatingMetricSeries[] }) {
  const isMix = category !== "kpi"
  return <Card>
    <CardHeader>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><div className="flex items-center gap-2"><CategoryIcon category={category} /><CardTitle>{categoryLabels[category]}</CardTitle></div><CardDescription className="mt-2">{isMix ? "Mix and growth use only compatible issuer-defined measures, units, reporting bases, and definition versions." : "Typed issuer-specific operating measures remain flexible without pretending they are standardized across companies."}</CardDescription></div>
        <Badge variant="outline">{series.length} reported series</Badge>
      </div>
    </CardHeader>
    <CardContent className="space-y-4">
      {series.length ? <>{isMix ? <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{series.map((item) => <MixCard key={item.definition.definitionId} series={item} />)}</div> : null}<EvidenceTable series={series} /></> : <div className="grid min-h-40 place-items-center rounded-lg border border-dashed text-center"><div><CategoryIcon category={category} /><h3 className="mt-3 font-semibold">No source-backed {categoryLabels[category].toLowerCase()}.</h3><p className="mt-2 max-w-md text-sm text-muted-foreground">Coverage follows the company&apos;s exact public reporting and may be unavailable or non-standardized.</p></div></div>}
    </CardContent>
  </Card>
}

export function OperationsIntelligence({ operations }: { operations: OperatingIntelligenceResponse | null }) {
  const byCategory = (category: OperatingMetricCategory) => operations?.series.filter((item) => item.definition.category === category) || []
  return <div className="space-y-4">
    <div className="flex justify-end"><Badge variant="outline">As of {operations ? new Date(operations.asOf).toLocaleString() : "unavailable"}</Badge></div>
    {operations?.transitions.length ? <Alert><AlertTriangle /><AlertTitle>Reporting Definitions Changed</AlertTitle><AlertDescription><div className="space-y-2">{operations.transitions.map((transition) => <div key={`${transition.priorDefinitionId}-${transition.nextDefinitionId}`} className="rounded-md border bg-background/40 p-3"><strong>{transition.priorLabel} → {transition.nextLabel}</strong><span className="mt-1 block text-xs">{transition.priorReportingBasis} → {transition.nextReportingBasis} · known {new Date(transition.knownAt).toLocaleDateString()}</span></div>)}</div><p className="mt-2">GBB does not calculate growth across incompatible definitions.</p></AlertDescription></Alert> : null}
    <OperatingSection category="segment" series={byCategory("segment")} />
    <OperatingSection category="geography" series={byCategory("geography")} />
    <OperatingSection category="kpi" series={byCategory("kpi")} />
    <Alert><ChartNoAxesColumnIncreasing /><AlertTitle>Issuer-Defined Operating Evidence</AlertTitle><AlertDescription>{operations?.warnings.join(" ") || "No operating evidence is loaded for this company. Missing coverage is not interpreted as zero."}</AlertDescription></Alert>
  </div>
}
