import { AlertCircle, CalendarClock, CheckCircle2, CircleDotDashed, Target, XCircle } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SourceEvidenceDialog } from "@/features/company-intelligence/source-evidence-dialog"
import type { GuidanceRecord, GuidanceStatus, GuidanceValueKind, GuidanceHistoryResponse } from "@/lib/types"

const statusLabels: Record<GuidanceStatus, string> = {
  open: "Open",
  delivered: "Delivered",
  partially_delivered: "Partially Delivered",
  missed: "Missed",
  withdrawn: "Withdrawn",
  superseded: "Superseded",
  unknown: "Unknown",
}

function readableDate(value: string) {
  return new Date(value).toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric" })
}

function valueText(record: GuidanceRecord) {
  const statement = record.statement
  if (statement.valueKind === "qualitative") return "Qualitative Commitment"
  if (statement.valueKind === "numeric_range") {
    if (statement.unit === "USD millions") return `$${statement.lowerBound?.toLocaleString()}M–$${statement.upperBound?.toLocaleString()}M`
    if (statement.unit === "USD billions") return `$${statement.lowerBound?.toLocaleString()}B–$${statement.upperBound?.toLocaleString()}B`
    if (statement.unit === "%") return `${statement.lowerBound?.toLocaleString()}%–${statement.upperBound?.toLocaleString()}%`
    return `${statement.lowerBound?.toLocaleString()}–${statement.upperBound?.toLocaleString()} ${statement.unit}`
  }
  const prefix = statement.comparison === "at_least" ? "At least " : statement.comparison === "at_most" ? "At most " : statement.comparison === "approximately" ? "Approximately " : ""
  if (statement.unit === "USD millions") return `${prefix}$${statement.pointValue?.toLocaleString()}M`
  if (statement.unit === "USD billions") return `${prefix}$${statement.pointValue?.toLocaleString()}B`
  if (statement.unit === "%") return `${prefix}${statement.pointValue?.toLocaleString()}%`
  return `${prefix}${statement.pointValue?.toLocaleString()} ${statement.unit}`
}

function statusVariant(status: GuidanceStatus): "default" | "secondary" | "destructive" | "outline" {
  if (status === "missed" || status === "withdrawn") return "destructive"
  if (status === "delivered") return "secondary"
  if (status === "open") return "default"
  return "outline"
}

function StatusIcon({ status }: { status: GuidanceStatus }) {
  if (status === "delivered") return <CheckCircle2 className="size-4 text-primary" />
  if (status === "missed" || status === "withdrawn") return <XCircle className="size-4 text-destructive" />
  return <CircleDotDashed className="size-4 text-muted-foreground" />
}

function kindLabel(kind: GuidanceValueKind) {
  return kind === "numeric_range" ? "Normalized Range" : kind === "numeric_point" ? "Normalized Point" : "Original Qualitative Wording"
}

function GuidanceCard({ record, index }: { record: GuidanceRecord; index: number }) {
  const statement = record.statement
  return <article className="relative grid gap-4 pl-8 sm:grid-cols-[180px_minmax(0,1fr)] sm:pl-10">
    <div className="absolute left-2 top-2 z-10 grid size-5 place-items-center rounded-full border bg-background sm:left-[11px]"><StatusIcon status={record.status} /></div>
    <div className="absolute bottom-[-1rem] left-[17px] top-7 w-px bg-border sm:left-5" aria-hidden="true" />
    <div className="pt-1 font-mono text-[10px] text-muted-foreground"><strong className="block text-xs text-foreground">{readableDate(statement.issuedAt)}</strong><span className="mt-1 block">Known {readableDate(statement.knownAt)}</span><span className="mt-2 block">Revision {statement.revision}</span><Badge variant="outline" className="mt-2">{record.revisionDirection}</Badge></div>
    <Card className="gap-4">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><div className="flex flex-wrap items-center gap-2"><Badge variant={statusVariant(record.status)}>{statusLabels[record.status]}</Badge><Badge variant="outline">{statement.statementType.replaceAll("_", " ")}</Badge><Badge variant="secondary">{kindLabel(statement.valueKind)}</Badge></div><CardTitle className="mt-3 text-lg">{statement.topic}</CardTitle><CardDescription className="mt-1">{statement.fiscalPeriod || "Applicable period"} {statement.fiscalYear || ""}{statement.applicablePeriodEnd ? ` · through ${statement.applicablePeriodEnd}` : ""}</CardDescription></div>
          <SourceEvidenceDialog evidence={record.statementEvidence} label="Original Source" title={`${statement.topic} source evidence`} />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-lg border bg-muted/25 p-4"><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">Persisted Normalization</span><strong className="mt-2 block text-xl">{valueText(record)}</strong><p className="mt-2 text-xs text-muted-foreground">{statement.valueKind === "qualitative" ? "No numeric value is inferred from ambiguous wording." : `${statement.comparison.replaceAll("_", " ")} · ${statement.metricId || "issuer-defined metric"}`}</p></div>
        <blockquote className="border-l-2 border-primary pl-4 text-sm italic leading-6">“{statement.statementText}”</blockquote>
        {record.evaluations.length ? <div className="space-y-2"><h4 className="text-sm font-semibold">Outcome History</h4>{record.evaluations.map((evaluation) => { const evidence = record.evaluationEvidence[evaluation.evaluationId] || []; return <div key={evaluation.evaluationId} className="flex flex-wrap items-start justify-between gap-3 rounded-lg border p-3"><div><div className="flex flex-wrap gap-2"><Badge variant={statusVariant(evaluation.status)}>{statusLabels[evaluation.status]}</Badge><Badge variant="outline">{evaluation.method.replaceAll("_", " ")}</Badge></div><p className="mt-2 text-xs text-muted-foreground">Evaluated {readableDate(evaluation.evaluatedAt)}{evaluation.actualValue === null ? "" : ` · actual ${evaluation.actualValue.toLocaleString()} ${evaluation.actualUnit}`}</p>{evaluation.note ? <p className="mt-2 text-sm">{evaluation.note}</p> : null}{evaluation.sourceFactIds.length ? <p className="mt-2 font-mono text-[10px] text-muted-foreground">{evaluation.sourceFactIds.length} normalized SEC source fact{evaluation.sourceFactIds.length === 1 ? "" : "s"}</p> : null}</div><SourceEvidenceDialog evidence={evidence} label="Outcome Source" title={`${statement.topic} outcome evidence`} /></div> })}</div> : <p className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground">No objective outcome has been persisted. Open does not mean likely or unlikely.</p>}
        <div className="font-mono text-[9px] text-muted-foreground">Timeline item {index + 1} · extraction {statement.extractionMethod} · model {statement.modelVersion}</div>
      </CardContent>
    </Card>
  </article>
}

export function GuidanceTimeline({ guidance }: { guidance: GuidanceHistoryResponse | null }) {
  const records = [...(guidance?.records || [])].sort((left, right) => left.statement.issuedAt.localeCompare(right.statement.issuedAt))
  return <div className="space-y-4">
    <Card><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex items-center gap-2"><Target className="size-4 text-primary" /><CardTitle>Management Guidance & Commitments</CardTitle></div><CardDescription className="mt-2">An immutable chronology of original statements, linked revisions, withdrawals, and evidence-backed outcomes.</CardDescription></div><div className="flex flex-wrap gap-2"><Badge variant="outline">{records.length} source-backed records</Badge><Badge variant="outline">As of {guidance ? new Date(guidance.asOf).toLocaleString() : "unavailable"}</Badge></div></div></CardHeader><CardContent>{records.length ? <div className="space-y-4">{records.map((record, index) => <GuidanceCard key={record.statement.statementId} record={record} index={index} />)}</div> : <div className="grid min-h-56 place-items-center rounded-lg border border-dashed text-center"><div><CalendarClock className="mx-auto size-8 text-muted-foreground" /><h3 className="mt-3 font-semibold">No source-backed guidance is available.</h3><p className="mt-2 max-w-md text-sm text-muted-foreground">GBB will not reconstruct or summarize commitments without an inspectable original statement.</p></div></div>}</CardContent></Card>
    <Alert><AlertCircle /><AlertTitle>Historical Record, Not Model Forecast</AlertTitle><AlertDescription>{guidance?.warnings.join(" ") || "No guidance coverage is loaded for this company."} Original excerpts remain authoritative; GBB does not replace them with an LLM summary.</AlertDescription></Alert>
  </div>
}
