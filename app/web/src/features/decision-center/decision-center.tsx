import { type FormEvent, type ReactNode, useCallback, useEffect, useMemo, useState } from "react"
import {
  AlertTriangle,
  BookOpenCheck,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Database,
  ExternalLink,
  FileText,
  Gauge,
  History,
  LoaderCircle,
  NotebookTabs,
  Plus,
  RefreshCw,
  Save,
  Search,
  ShieldAlert,
  Target,
  TrendingDown,
  WalletCards,
  X,
} from "lucide-react"
import { toast } from "sonner"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import {
  compareDecisionExpressions,
  createDecisionRecord,
  loadDecisionCenter,
  loadDecisionRecords,
  runDecisionStressTest,
  saveEntryPlan,
  savePositionIntent,
  saveThesisCard,
  updateDecisionRecord,
} from "@/lib/api"
import { labHref, normalizeTicker } from "@/lib/navigation"
import type {
  DecisionCenterWorkspace,
  DecisionJournalRecord,
  DecisionObjective,
  DecisionState,
  DecisionType,
  EntryPlanInput,
  EntryTrancheInput,
  EvidenceStrength,
  ExpressionComparison,
  InstrumentExpression,
  InstrumentFitResult,
  LaterOutcome,
  MoatAssessment,
  PolicyCheck,
  PositionIntentInput,
  ProcessReview,
  StressScenarioInput,
  StressTestResult,
  ThesisCardInput,
  ThesisEvidenceLinkInput,
  ThesisStatus,
} from "@/lib/types"
import { cn } from "@/lib/utils"

const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })
const preciseCurrency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 })
const today = new Date()
const initialTargetDate = new Date(today.getFullYear(), today.getMonth() + 3, today.getDate()).toISOString().slice(0, 10)

const statusLabels: Record<ThesisStatus, string> = {
  watch: "Watch",
  insufficient_evidence: "Insufficient Evidence",
  ready_for_position_planning: "Ready For Position Planning",
  invalidated: "Invalidated",
}

const objectiveLabels: Record<DecisionObjective, string> = {
  ownership_now: "Own Now",
  accumulate_lower: "Accumulate Lower",
  income: "Generate Income",
  defined_risk_upside: "Defined-Risk Upside",
}

const decisionStateLabels: Record<DecisionState, string> = {
  planned: "Planned",
  entered: "Entered",
  partially_entered: "Partially Entered",
  missed: "Missed",
  cancelled: "Cancelled",
  invalidated: "Invalidated",
  closed: "Closed",
  passed: "Passed",
}

const decisionTypeLabels: Record<DecisionType, string> = {
  ownership: "Ownership",
  accumulation: "Accumulation",
  income: "Income",
  defined_risk: "Defined Risk",
  risk_reduction: "Risk Reduction",
  pass: "Pass",
}

const emptyThesis: ThesisCardInput = {
  status: "watch",
  evidence_strength: "unknown",
  moat_assessment: "unknown",
  major_risks: [],
  catalysts: [],
  invalidation_criteria: [],
  rationale: "",
  evidence_links: [],
}

const emptyIntent: PositionIntentInput = {
  target_amount: null,
  target_percent: null,
  maximum_amount: null,
  maximum_percent: null,
  current_price: null,
}

const emptyProcessReview: ProcessReview = {
  thesis_evidence_sufficient: "unreviewed",
  position_inside_risk_budget: "unreviewed",
  instrument_fit_intended_exposure: "unreviewed",
  execution_followed_plan: "unreviewed",
  exit_followed_rule: "unreviewed",
  process_quality: "unreviewed",
  notes: "",
}

const defaultTranches: EntryTrancheInput[] = [
  { label: "Starter", allocation_amount: null, allocation_percent: 25, status: "planned", trigger: "Establish a small position inside the stated maximum.", rationale: "Gain measured exposure without committing the full risk budget.", preferred_entry_price: null, maximum_acceptable_execution_price: null },
  { label: "Confirmation", allocation_amount: null, allocation_percent: 50, status: "planned", trigger: "Add only after thesis evidence or price behavior confirms the plan.", rationale: "Reserve the largest tranche for confirmation rather than urgency.", preferred_entry_price: null, maximum_acceptable_execution_price: null },
  { label: "Opportunity Reserve", allocation_amount: null, allocation_percent: 25, status: "available", trigger: "Use only if price improves while the thesis remains intact.", rationale: "Keep flexibility for volatility without exceeding the maximum exposure.", preferred_entry_price: null, maximum_acceptable_execution_price: null },
]

const defaultStressScenarios: StressScenarioInput[] = [
  { underlying_change_percent: -20, iv_change_percent: 25, days_forward: 30 },
  { underlying_change_percent: -40, iv_change_percent: 50, days_forward: 60 },
  { underlying_change_percent: -60, iv_change_percent: 50, days_forward: 90 },
]

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The local research service did not complete this request."
}

function optionalNumber(value: string) {
  if (!value.trim()) return null
  const number = Number(value)
  if (!Number.isFinite(number)) throw new Error("Enter a valid number or leave the field blank.")
  return number
}

function splitLines(value: string) {
  return value.split("\n").map((item) => item.trim()).filter(Boolean)
}

function lines(value: string[]) {
  return value.join("\n")
}

function Field({ label, hint, children, className }: { label: string; hint?: string; children: ReactNode; className?: string }) {
  return <label className={cn("grid min-w-0 gap-1.5 text-sm", className)}><span className="font-medium">{label}</span>{children}{hint ? <span className="text-xs leading-5 text-muted-foreground">{hint}</span> : null}</label>
}

function SummaryMetric({ label, value, tone }: { label: string; value: ReactNode; tone?: "positive" | "negative" }) {
  return <div className="min-w-0 bg-card/70 px-4 py-3"><dt className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">{label}</dt><dd className={cn("mt-1 truncate text-lg font-semibold", tone === "positive" && "text-primary", tone === "negative" && "text-destructive")}>{value}</dd></div>
}

function GateBadge({ status }: { status: PolicyCheck["status"] | InstrumentFitResult["overall_status"] }) {
  const variant = status === "pass" ? "default" : status === "fail" ? "destructive" : "outline"
  return <Badge variant={variant} className={cn("uppercase", status === "incomplete" && "border-amber-400/50 text-amber-300", status === "warn" && "border-amber-400/50 text-amber-300")}>{status.replace("_", " ")}</Badge>
}

function DecisionChain({ workspace }: { workspace: DecisionCenterWorkspace | null }) {
  const stages = [
    { label: "Thesis", complete: Boolean(workspace?.thesis), detail: workspace?.thesis ? statusLabels[workspace.thesis.status] : "Define evidence" },
    { label: "Risk", complete: Boolean(workspace?.risk_policy && workspace.position_intent?.is_complete), detail: workspace?.risk_policy ? `Policy v${workspace.risk_policy.version}` : "Set policy" },
    { label: "Expression", complete: Boolean(workspace?.entry_plans[0]?.expression), detail: workspace?.entry_plans[0]?.expression.name || "Compare instruments" },
    { label: "Entry", complete: Boolean(workspace?.entry_plans.length), detail: workspace?.entry_plans[0] ? `${workspace.entry_plans[0].tranches.length} tranches` : "Stage exposure" },
    { label: "Journal", complete: Boolean(workspace?.decisions.length), detail: workspace?.decisions[0] ? decisionStateLabels[workspace.decisions[0].state as DecisionState] : "Preserve decision" },
  ]
  return <ol aria-label="Decision workflow" className="grid overflow-hidden rounded-lg border bg-border sm:grid-cols-5">{stages.map((stage, index) => <li key={stage.label} className="relative bg-card px-4 py-3"><div className="flex items-center gap-2"><span className={cn("grid size-6 shrink-0 place-items-center rounded-full border font-mono text-[10px]", stage.complete ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground/30 text-muted-foreground")}>{stage.complete ? <CheckCircle2 className="size-3.5" /> : index + 1}</span><strong className="text-sm">{stage.label}</strong>{index < stages.length - 1 ? <ChevronRight className="ml-auto hidden size-3 text-muted-foreground sm:block" /> : null}</div><p className="mt-1 truncate pl-8 text-[10px] text-muted-foreground">{stage.detail}</p></li>)}</ol>
}

function ThesisWorkspace({ workspace, onSaved }: { workspace: DecisionCenterWorkspace; onSaved: (workspace: DecisionCenterWorkspace) => void }) {
  const [form, setForm] = useState<ThesisCardInput>(() => workspace.thesis ? {
    status: workspace.thesis.status,
    evidence_strength: workspace.thesis.evidence_strength,
    moat_assessment: workspace.thesis.moat_assessment,
    major_risks: workspace.thesis.major_risks,
    catalysts: workspace.thesis.catalysts,
    invalidation_criteria: workspace.thesis.invalidation_criteria,
    rationale: workspace.thesis.rationale,
    evidence_links: workspace.thesis.evidence_references.map(({ span_id, role, interpretation }) => ({ span_id, role, interpretation })),
  } : emptyThesis)
  const [riskText, setRiskText] = useState(lines(form.major_risks))
  const [catalystText, setCatalystText] = useState(lines(form.catalysts))
  const [invalidationText, setInvalidationText] = useState(lines(form.invalidation_criteria))
  const [saving, setSaving] = useState(false)

  const updateEvidence = (index: number, patch: Partial<ThesisEvidenceLinkInput>) => {
    setForm((current) => ({ ...current, evidence_links: current.evidence_links.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) }))
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    try {
      const thesis = await saveThesisCard(workspace.ticker, {
        ...form,
        major_risks: splitLines(riskText),
        catalysts: splitLines(catalystText),
        invalidation_criteria: splitLines(invalidationText),
        evidence_links: form.evidence_links.filter((item) => item.span_id.trim()),
      })
      onSaved({ ...workspace, thesis })
      toast.success(`Thesis version ${thesis.version} saved.`, { description: "Its status changed only because you selected it." })
    } catch (error) {
      toast.error("Thesis was not saved", { description: errorMessage(error) })
    } finally {
      setSaving(false)
    }
  }

  return <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)]">
    <Card className="gap-0 overflow-hidden"><CardHeader className="border-b"><div className="flex flex-wrap items-center justify-between gap-3"><div><CardTitle>Investment Thesis</CardTitle><CardDescription className="mt-1 max-w-2xl">Record what you believe, why, and what would prove it wrong. Missing network, operations, or guidance data never promotes or blocks this user-owned status.</CardDescription></div>{workspace.thesis ? <Badge variant="outline">Version {workspace.thesis.version}</Badge> : <Badge variant="secondary">Draft</Badge>}</div></CardHeader><CardContent className="pt-5"><form className="space-y-5" onSubmit={(event) => void submit(event)}>
      <div className="grid gap-4 md:grid-cols-3"><Field label="Research Status" hint="Only you can change this status."><Select value={form.status} onValueChange={(value) => setForm((current) => ({ ...current, status: value as ThesisStatus }))}><SelectTrigger aria-label="Thesis status"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(statusLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></Field><Field label="Evidence Strength"><Select value={form.evidence_strength} onValueChange={(value) => setForm((current) => ({ ...current, evidence_strength: value as EvidenceStrength }))}><SelectTrigger aria-label="Evidence strength"><SelectValue /></SelectTrigger><SelectContent>{["unknown", "limited", "moderate", "strong"].map((value) => <SelectItem key={value} value={value}>{value.replace("_", " ")}</SelectItem>)}</SelectContent></Select></Field><Field label="Moat Assessment"><Select value={form.moat_assessment} onValueChange={(value) => setForm((current) => ({ ...current, moat_assessment: value as MoatAssessment }))}><SelectTrigger aria-label="Moat assessment"><SelectValue /></SelectTrigger><SelectContent>{["unknown", "none", "limited", "moderate", "strong"].map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent></Select></Field></div>
      <Field label="Your Interpretation" hint="Keep interpretation separate from sourced excerpts attached below."><Textarea aria-label="Thesis rationale" className="min-h-28" maxLength={5000} value={form.rationale} onChange={(event) => setForm((current) => ({ ...current, rationale: event.target.value }))} placeholder="State the economic thesis, not a price prediction." /></Field>
      <div className="grid gap-4 lg:grid-cols-3"><Field label="Major Risks" hint="One risk per line."><Textarea aria-label="Major risks" className="min-h-32" value={riskText} onChange={(event) => setRiskText(event.target.value)} /></Field><Field label="Catalysts" hint="One possible catalyst per line."><Textarea aria-label="Catalysts" className="min-h-32" value={catalystText} onChange={(event) => setCatalystText(event.target.value)} /></Field><Field label="Invalidation Criteria" hint="Required before Ready or Invalidated status."><Textarea aria-label="Invalidation criteria" className="min-h-32" value={invalidationText} onChange={(event) => setInvalidationText(event.target.value)} /></Field></div>
      <details className="group rounded-lg border bg-muted/10"><summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-medium">Attach Source Evidence <Badge variant="outline">{form.evidence_links.length}</Badge></summary><div className="space-y-3 border-t p-4"><p className="text-xs leading-5 text-muted-foreground">Paste a stable evidence span ID from Company Intelligence. GBB validates it locally and stores the exact excerpt, source URL, and known-at time beside your interpretation.</p>{form.evidence_links.map((item, index) => <div key={`${index}-${item.span_id}`} className="grid gap-3 rounded-md border bg-card/60 p-3 md:grid-cols-[minmax(180px,0.8fr)_160px_minmax(220px,1.4fr)_auto]"><Field label="Evidence Span ID"><Input aria-label={`Evidence span ${index + 1}`} value={item.span_id} onChange={(event) => updateEvidence(index, { span_id: event.target.value })} /></Field><Field label="Role"><Select value={item.role} onValueChange={(value) => updateEvidence(index, { role: value as ThesisEvidenceLinkInput["role"] })}><SelectTrigger aria-label={`Evidence role ${index + 1}`}><SelectValue /></SelectTrigger><SelectContent><SelectItem value="support">Support</SelectItem><SelectItem value="context">Context</SelectItem><SelectItem value="contradiction">Contradiction</SelectItem></SelectContent></Select></Field><Field label="Your Interpretation"><Input aria-label={`Evidence interpretation ${index + 1}`} value={item.interpretation} onChange={(event) => updateEvidence(index, { interpretation: event.target.value })} /></Field><Button type="button" size="icon" variant="ghost" className="self-end" aria-label={`Remove evidence ${index + 1}`} onClick={() => setForm((current) => ({ ...current, evidence_links: current.evidence_links.filter((_, itemIndex) => itemIndex !== index) }))}><X /></Button></div>)}<Button type="button" variant="outline" size="sm" onClick={() => setForm((current) => ({ ...current, evidence_links: [...current.evidence_links, { span_id: "", role: "support", interpretation: "" }] }))}><Plus />Add Evidence Reference</Button></div></details>
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="max-w-xl text-xs leading-5 text-muted-foreground">Saving creates a new immutable version. It does not automatically authorize a position.</p><Button type="submit" disabled={saving}>{saving ? <LoaderCircle className="motion-safe:animate-spin" /> : <Save />}Save Thesis Version</Button></div>
    </form></CardContent></Card>
    <aside className="space-y-4"><Card className="gap-0"><CardHeader><CardTitle className="text-base">Sourced Evidence</CardTitle><CardDescription>Exact excerpts remain distinct from your interpretation.</CardDescription></CardHeader><CardContent className="space-y-3">{workspace.thesis?.evidence_references.length ? workspace.thesis.evidence_references.map((reference) => <article key={reference.span_id} className="rounded-md border border-primary/20 bg-muted/20 p-3"><div className="flex flex-wrap items-center gap-2"><Badge variant="outline">{reference.role}</Badge><span className="font-mono text-[9px] text-muted-foreground">KNOWN {new Date(reference.known_at).toLocaleDateString()}</span></div><blockquote className="mt-3 text-sm leading-6">“{reference.exact_text}”</blockquote>{reference.interpretation ? <p className="mt-3 border-t pt-3 text-xs leading-5 text-muted-foreground"><strong className="text-foreground">Interpretation:</strong> {reference.interpretation}</p> : null}<a className="mt-3 inline-flex items-center gap-1 text-xs text-primary hover:underline" href={reference.source_url} target="_blank" rel="noreferrer">{reference.source}<ExternalLink className="size-3" /></a></article>) : <div className="rounded-lg border border-dashed p-5 text-sm leading-6 text-muted-foreground">No source spans attached yet. A thesis may remain on Watch without every Company Intelligence module being available.</div>}</CardContent></Card><Button asChild variant="outline" className="w-full"><a href={labHref("intelligence", workspace.ticker)}><BookOpenCheck />Review Company Evidence</a></Button></aside>
  </div>
}

function PositionAndExpressionWorkspace({ workspace, onWorkspaceChange, selectedExpression, onSelectExpression }: { workspace: DecisionCenterWorkspace; onWorkspaceChange: (workspace: DecisionCenterWorkspace) => void; selectedExpression: InstrumentExpression | null; onSelectExpression: (expression: InstrumentExpression) => void }) {
  const [intent, setIntent] = useState(() => ({
    targetAmount: workspace.position_intent?.target_amount === null || workspace.position_intent?.target_amount === undefined ? "" : String(workspace.position_intent.target_amount),
    targetPercent: workspace.position_intent?.target_percent === null || workspace.position_intent?.target_percent === undefined ? "" : String(workspace.position_intent.target_percent),
    maximumAmount: workspace.position_intent?.maximum_amount === null || workspace.position_intent?.maximum_amount === undefined ? "" : String(workspace.position_intent.maximum_amount),
    maximumPercent: workspace.position_intent?.maximum_percent === null || workspace.position_intent?.maximum_percent === undefined ? "" : String(workspace.position_intent.maximum_percent),
    currentPrice: workspace.position_intent ? "" : "",
  }))
  const [objective, setObjective] = useState<DecisionObjective>("ownership_now")
  const [targetDate, setTargetDate] = useState(initialTargetDate)
  const [targetPrice, setTargetPrice] = useState("")
  const [sharePrice, setSharePrice] = useState("")
  const [comparison, setComparison] = useState<ExpressionComparison | null>(null)
  const [saving, setSaving] = useState(false)
  const [comparing, setComparing] = useState(false)

  const submitIntent = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    try {
      const result = await savePositionIntent(workspace.ticker, {
        target_amount: optionalNumber(intent.targetAmount),
        target_percent: optionalNumber(intent.targetPercent),
        maximum_amount: optionalNumber(intent.maximumAmount),
        maximum_percent: optionalNumber(intent.maximumPercent),
        current_price: optionalNumber(intent.currentPrice),
      })
      onWorkspaceChange({ ...workspace, position_intent: result })
      toast.success(`Position intent version ${result.version} saved.`)
    } catch (error) {
      toast.error("Position intent was not saved", { description: errorMessage(error) })
    } finally {
      setSaving(false)
    }
  }

  const compare = async () => {
    if (!workspace.position_intent) return
    setComparing(true)
    try {
      const result = await compareDecisionExpressions(workspace.ticker, {
        position_intent_id: workspace.position_intent.intent_id,
        objective,
        target_date: targetDate,
        target_price: optionalNumber(targetPrice),
        share_price: optionalNumber(sharePrice),
      })
      setComparison(result)
      if (!selectedExpression && result.candidates[0]) onSelectExpression(result.candidates[0].expression)
      toast.success(`${result.candidates.length} eligible expressions compared.`, { description: "No candidate is labelled optimal." })
    } catch (error) {
      toast.error("Instrument comparison failed", { description: errorMessage(error) })
    } finally {
      setComparing(false)
    }
  }

  return <div className="space-y-5">
    {!workspace.risk_policy ? <Alert><ShieldAlert /><AlertTitle>Personal Risk Policy Missing</AlertTitle><AlertDescription>Position sizing can be saved, but every policy gate will remain incomplete until Portfolio &amp; Risk is configured.</AlertDescription></Alert> : null}
    <div className="grid gap-5 xl:grid-cols-[minmax(320px,0.7fr)_minmax(0,1.3fr)]"><Card className="gap-0"><CardHeader className="border-b"><CardTitle>Desired Exposure</CardTitle><CardDescription>Size the company exposure before selecting shares or options.</CardDescription></CardHeader><CardContent className="pt-5"><form className="space-y-4" onSubmit={(event) => void submitIntent(event)}><div className="grid gap-4 sm:grid-cols-2"><Field label="Target %" hint="Preferred portfolio footprint."><Input aria-label="Target exposure percent" type="number" min="0.01" max="100" step="0.01" value={intent.targetPercent} onChange={(event) => setIntent((current) => ({ ...current, targetPercent: event.target.value }))} /></Field><Field label="Maximum %" hint="Hard company-level ceiling."><Input aria-label="Maximum exposure percent" type="number" min="0.01" max="100" step="0.01" value={intent.maximumPercent} onChange={(event) => setIntent((current) => ({ ...current, maximumPercent: event.target.value }))} /></Field></div><details className="rounded-lg border bg-muted/10"><summary className="cursor-pointer px-4 py-3 text-sm font-medium">Amount Overrides &amp; Manual Price</summary><div className="grid gap-4 border-t p-4 sm:grid-cols-2"><Field label="Target Amount"><Input aria-label="Target exposure amount" type="number" min="0.01" step="0.01" value={intent.targetAmount} onChange={(event) => setIntent((current) => ({ ...current, targetAmount: event.target.value }))} /></Field><Field label="Maximum Amount"><Input aria-label="Maximum exposure amount" type="number" min="0.01" step="0.01" value={intent.maximumAmount} onChange={(event) => setIntent((current) => ({ ...current, maximumAmount: event.target.value }))} /></Field><Field label="Current Share Price" hint="Optional fallback if market data is unavailable."><Input aria-label="Current share price" type="number" min="0.01" step="0.01" value={intent.currentPrice} onChange={(event) => setIntent((current) => ({ ...current, currentPrice: event.target.value }))} /></Field></div></details><Button type="submit" disabled={saving}>{saving ? <LoaderCircle className="motion-safe:animate-spin" /> : <Save />}Save Position Intent</Button></form>{workspace.position_intent ? <dl className="mt-5 grid gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-2"><SummaryMetric label="Current Exposure" value={workspace.position_intent.current_exposure_percent === null ? "Unknown" : `${workspace.position_intent.current_exposure_percent.toFixed(2)}%`} /><SummaryMetric label="Current Shares" value={workspace.position_intent.current_shares.toLocaleString()} /><SummaryMetric label="Target" value={workspace.position_intent.target_percent === null ? currency.format(workspace.position_intent.target_amount || 0) : `${workspace.position_intent.target_percent}%`} /><SummaryMetric label="Maximum" value={workspace.position_intent.maximum_percent === null ? currency.format(workspace.position_intent.maximum_amount || 0) : `${workspace.position_intent.maximum_percent}%`} /></dl> : null}</CardContent></Card>
      <Card className="gap-0"><CardHeader className="border-b"><div className="flex flex-wrap items-center justify-between gap-3"><div><CardTitle>Instrument Fit Comparator</CardTitle><CardDescription>Compare how supported instruments express the same position intent. This is not an optimizer.</CardDescription></div><Badge variant="outline">Shares · CSP · Defined Risk</Badge></div></CardHeader><CardContent className="space-y-5 pt-5"><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{(Object.keys(objectiveLabels) as DecisionObjective[]).map((value) => <Button key={value} type="button" variant={objective === value ? "default" : "outline"} className="h-auto min-h-14 whitespace-normal" onClick={() => setObjective(value)}>{objectiveLabels[value]}</Button>)}</div><div className="grid gap-4 md:grid-cols-3"><Field label="Decision Horizon"><Input aria-label="Decision target date" type="date" min={new Date().toISOString().slice(0, 10)} value={targetDate} onChange={(event) => setTargetDate(event.target.value)} /></Field><Field label="Target Share Price" hint="Optional scenario input."><Input aria-label="Target share price" type="number" min="0.01" step="0.01" value={targetPrice} onChange={(event) => setTargetPrice(event.target.value)} /></Field><Field label="Manual Current Price" hint="Optional provider fallback."><Input aria-label="Comparison share price" type="number" min="0.01" step="0.01" value={sharePrice} onChange={(event) => setSharePrice(event.target.value)} /></Field></div><div className="flex flex-wrap items-center gap-3"><Button type="button" disabled={!workspace.position_intent || comparing} onClick={() => void compare()}>{comparing ? <LoaderCircle className="motion-safe:animate-spin" /> : <Gauge />}Compare Expressions</Button><span className="text-xs text-muted-foreground">Target and maximum exposure remain unchanged across candidates.</span></div></CardContent></Card></div>
    {comparison ? <section aria-label="Instrument comparison results" className="space-y-4"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">Expression Trade-Offs</h2><p className="mt-1 text-sm text-muted-foreground">Select an expression to carry into entry planning and stress testing.</p></div><div className="flex gap-2"><Button asChild size="sm" variant="outline"><a href={comparison.strategy_lab_url}>Strategy Lab<ExternalLink /></a></Button><Button asChild size="sm" variant="outline"><a href={comparison.option_lab_url}>Option Lab<ExternalLink /></a></Button></div></div>{comparison.warnings.length ? <Alert><AlertTriangle /><AlertTitle>Comparison Limitations</AlertTitle><AlertDescription>{comparison.warnings.join(" ")}</AlertDescription></Alert> : null}<div className="grid gap-4 lg:grid-cols-2">{comparison.candidates.map((candidate) => <ExpressionCard key={candidate.candidate_id} candidate={candidate} selected={selectedExpression?.name === candidate.expression.name} onSelect={() => onSelectExpression(candidate.expression)} />)}</div></section> : null}
  </div>
}

function ExpressionCard({ candidate, selected, onSelect }: { candidate: InstrumentFitResult; selected: boolean; onSelect: () => void }) {
  return <Card className={cn("gap-0 overflow-hidden transition-colors", selected && "border-primary ring-1 ring-primary/30")}><CardHeader className="border-b"><div className="flex items-start justify-between gap-3"><div><CardTitle className="text-base">{candidate.expression.name}</CardTitle><CardDescription className="mt-1">{candidate.objective_fit}</CardDescription></div><GateBadge status={candidate.overall_status} /></div></CardHeader><CardContent className="space-y-4 pt-4"><dl className="grid gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-3"><SummaryMetric label="Capital" value={candidate.capital_required === null ? "Unknown" : currency.format(candidate.capital_required)} /><SummaryMetric label="Collateral" value={candidate.collateral_required === null ? "—" : currency.format(candidate.collateral_required)} /><SummaryMetric label="Footprint" value={candidate.portfolio_footprint_percent === null ? "Unknown" : `${candidate.portfolio_footprint_percent.toFixed(2)}%`} /></dl><div className="grid gap-3 text-sm sm:grid-cols-2"><div><span className="text-xs text-muted-foreground">Upside</span><p className="mt-1 leading-5">{candidate.upside_character}</p></div><div><span className="text-xs text-muted-foreground">Downside</span><p className="mt-1 leading-5">{candidate.downside_character}</p></div></div>{candidate.assignment_obligation > 0 ? <div className="rounded-md border border-amber-400/30 bg-amber-400/5 p-3 text-sm"><strong>Assignment Obligation</strong><p className="mt-1 text-muted-foreground">{currency.format(candidate.assignment_obligation)} · {candidate.shares_after_assignment?.toLocaleString() || 0} shares after assignment · effective basis {candidate.effective_acquisition_basis === null ? "unknown" : preciseCurrency.format(candidate.effective_acquisition_basis)}</p></div> : null}<details className="rounded-md border"><summary className="cursor-pointer px-3 py-2 text-xs font-medium">Policy Gates ({candidate.checks.length})</summary><div className="space-y-2 border-t p-3">{candidate.checks.map((check) => <div key={check.key} className="grid gap-1 rounded-md bg-muted/20 p-2 text-xs sm:grid-cols-[110px_1fr]"><GateBadge status={check.status} /><div><strong>{check.label}</strong><p className="mt-1 leading-5 text-muted-foreground">{check.reason}</p><code className="mt-1 block overflow-x-auto text-[10px] text-muted-foreground">{check.arithmetic}</code></div></div>)}</div></details><Button type="button" variant={selected ? "default" : "outline"} className="w-full" onClick={onSelect}>{selected ? <CheckCircle2 /> : <Target />}{selected ? "Selected For Planning" : "Use This Expression"}</Button></CardContent></Card>
}

function EntryAndStressWorkspace({ workspace, selectedExpression, onWorkspaceChange }: { workspace: DecisionCenterWorkspace; selectedExpression: InstrumentExpression | null; onWorkspaceChange: (workspace: DecisionCenterWorkspace) => void }) {
  const existingPlan = workspace.entry_plans[0] || null
  const expression = selectedExpression || existingPlan?.expression || null
  const [executionMode, setExecutionMode] = useState<EntryPlanInput["execution_mode"]>(existingPlan?.execution_mode || "patient")
  const [escapePlan, setEscapePlan] = useState<EntryPlanInput["escape_plan"]>(existingPlan?.escape_plan || "reassess_thesis")
  const [notes, setNotes] = useState(existingPlan?.notes || "")
  const [tranches, setTranches] = useState<EntryTrancheInput[]>(existingPlan?.tranches.map(({ tranche_id: _trancheId, resolved_allocation_amount: _resolvedAmount, resolved_allocation_percent: _resolvedPercent, ...tranche }) => tranche) || defaultTranches)
  const [saving, setSaving] = useState(false)
  const [stressLoading, setStressLoading] = useState(false)
  const [stress, setStress] = useState<StressTestResult | null>(null)

  const updateTranche = (index: number, patch: Partial<EntryTrancheInput>) => setTranches((current) => current.map((tranche, itemIndex) => itemIndex === index ? { ...tranche, ...patch } : tranche))

  const save = async () => {
    if (!workspace.position_intent || !expression) return
    setSaving(true)
    try {
      const plan = await saveEntryPlan(workspace.ticker, {
        position_intent_id: workspace.position_intent.intent_id,
        expression,
        execution_mode: executionMode,
        escape_plan: escapePlan,
        tranches,
        notes,
      }, existingPlan?.entry_plan_id)
      onWorkspaceChange({ ...workspace, entry_plans: [plan, ...workspace.entry_plans.filter((item) => item.entry_plan_id !== existingPlan?.entry_plan_id)] })
      toast.success(`Entry plan version ${plan.version} saved.`)
    } catch (error) {
      toast.error("Entry plan was not saved", { description: errorMessage(error) })
    } finally {
      setSaving(false)
    }
  }

  const runStress = async () => {
    if (!workspace.position_intent || !expression) return
    setStressLoading(true)
    try {
      const result = await runDecisionStressTest(workspace.ticker, workspace.position_intent.intent_id, expression, defaultStressScenarios)
      setStress(result)
      toast.success("Stress gates recalculated server-side.")
    } catch (error) {
      toast.error("Stress test failed", { description: errorMessage(error) })
    } finally {
      setStressLoading(false)
    }
  }

  if (!workspace.position_intent || !expression) return <Alert><Target /><AlertTitle>Select Position Intent And Expression</AlertTitle><AlertDescription>Save desired exposure, compare supported instruments, and choose one before staging entries or running stress tests.</AlertDescription></Alert>

  return <div className="space-y-5"><div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(300px,0.7fr)]"><Card className="gap-0"><CardHeader className="border-b"><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>Staged Entry Planner</CardTitle><CardDescription className="mt-1">Plan exposure in deliberate tranches and define what happens if price escapes without you.</CardDescription></div><Badge variant="secondary">{expression.name}</Badge></div></CardHeader><CardContent className="space-y-5 pt-5"><div className="grid gap-4 md:grid-cols-2"><Field label="Execution Mode"><Select value={executionMode} onValueChange={(value) => setExecutionMode(value as EntryPlanInput["execution_mode"])}><SelectTrigger aria-label="Entry execution mode"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="patient">Patient</SelectItem><SelectItem value="establish_exposure">Establish Exposure</SelectItem><SelectItem value="catalyst">Catalyst-Aware</SelectItem></SelectContent></Select></Field><Field label="If Price Escapes"><Select value={escapePlan} onValueChange={(value) => setEscapePlan(value as EntryPlanInput["escape_plan"])}><SelectTrigger aria-label="Entry escape plan"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="abandon_wait">Abandon And Wait</SelectItem><SelectItem value="reassess_thesis">Reassess Thesis</SelectItem><SelectItem value="allow_starter_within_maximum">Allow Starter Within Maximum</SelectItem></SelectContent></Select></Field></div><div className="space-y-3">{tranches.map((tranche, index) => <article key={`${tranche.label}-${index}`} className="rounded-lg border bg-card/50 p-4"><div className="grid gap-4 md:grid-cols-[minmax(140px,0.7fr)_120px_150px_minmax(180px,1fr)_auto]"><Field label="Tranche"><Input aria-label={`Tranche ${index + 1} label`} value={tranche.label} onChange={(event) => updateTranche(index, { label: event.target.value })} /></Field><Field label="Allocation %"><Input aria-label={`Tranche ${index + 1} allocation percent`} type="number" min="0" max="100" step="0.01" value={tranche.allocation_percent ?? ""} onChange={(event) => updateTranche(index, { allocation_percent: optionalNumber(event.target.value), allocation_amount: null })} /></Field><Field label="Status"><Select value={tranche.status} onValueChange={(value) => updateTranche(index, { status: value as EntryTrancheInput["status"] })}><SelectTrigger aria-label={`Tranche ${index + 1} status`}><SelectValue /></SelectTrigger><SelectContent>{["planned", "available", "used", "skipped", "cancelled"].map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent></Select></Field><Field label="Trigger"><Input aria-label={`Tranche ${index + 1} trigger`} value={tranche.trigger} onChange={(event) => updateTranche(index, { trigger: event.target.value })} /></Field><Button type="button" size="icon" variant="ghost" className="self-end" aria-label={`Remove tranche ${index + 1}`} disabled={tranches.length === 1} onClick={() => setTranches((current) => current.filter((_, itemIndex) => itemIndex !== index))}><X /></Button></div><div className="mt-4 grid gap-4 md:grid-cols-3"><Field label="Preferred Price"><Input aria-label={`Tranche ${index + 1} preferred price`} type="number" min="0.01" step="0.01" value={tranche.preferred_entry_price ?? ""} onChange={(event) => updateTranche(index, { preferred_entry_price: optionalNumber(event.target.value) })} /></Field><Field label="Maximum Acceptable Price"><Input aria-label={`Tranche ${index + 1} maximum price`} type="number" min="0.01" step="0.01" value={tranche.maximum_acceptable_execution_price ?? ""} onChange={(event) => updateTranche(index, { maximum_acceptable_execution_price: optionalNumber(event.target.value) })} /></Field><Field label="Rationale"><Input aria-label={`Tranche ${index + 1} rationale`} value={tranche.rationale} onChange={(event) => updateTranche(index, { rationale: event.target.value })} /></Field></div></article>)}</div><div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="outline" onClick={() => setTranches((current) => [...current, { ...defaultTranches[0], label: `Tranche ${current.length + 1}`, allocation_percent: 0 }])}><Plus />Add Tranche</Button></div><Field label="Plan Notes"><Textarea aria-label="Entry plan notes" value={notes} onChange={(event) => setNotes(event.target.value)} /></Field><div className="flex flex-wrap justify-end gap-2"><Button type="button" variant="outline" disabled={stressLoading} onClick={() => void runStress()}>{stressLoading ? <LoaderCircle className="motion-safe:animate-spin" /> : <TrendingDown />}Run Stress Gates</Button><Button type="button" disabled={saving} onClick={() => void save()}>{saving ? <LoaderCircle className="motion-safe:animate-spin" /> : <Save />}Save Entry Plan</Button></div></CardContent></Card>
      <Card className="gap-0"><CardHeader><CardTitle className="text-base">Allocation Ledger</CardTitle><CardDescription>Unallocated capital remains a deliberate reserve.</CardDescription></CardHeader><CardContent>{existingPlan ? <dl className="grid gap-px overflow-hidden rounded-lg border bg-border"><SummaryMetric label="Target Allocation" value={currency.format(existingPlan.target_allocation_amount)} /><SummaryMetric label="Allocated" value={currency.format(existingPlan.allocated_amount)} /><SummaryMetric label="Opportunity Reserve" value={currency.format(existingPlan.unallocated_reserve)} tone={existingPlan.unallocated_reserve >= 0 ? "positive" : "negative"} /></dl> : <div className="rounded-lg border border-dashed p-5 text-sm leading-6 text-muted-foreground">Save the first plan to resolve every tranche into dollars and preserve a versioned allocation ledger.</div>}<Separator className="my-5" /><div className="space-y-3"><h3 className="text-sm font-semibold">Expression Snapshot</h3><p className="text-sm leading-6 text-muted-foreground">{expression.name}. Changes in Option Lab do not rewrite a saved plan or journal snapshot.</p></div></CardContent></Card></div>
    {stress ? <StressResults result={stress} /> : null}
  </div>
}

function StressResults({ result }: { result: StressTestResult }) {
  return <section aria-label="Stress test results" className="space-y-4"><div><h2 className="text-xl font-semibold">Position &amp; Portfolio Stress</h2><p className="mt-1 text-sm text-muted-foreground">Server-priced scenarios combine stock drawdown, IV expansion, and time decay. They are deterministic scenario tests, not forecasts.</p></div><div className="grid gap-4 lg:grid-cols-3">{result.scenarios.map((scenario) => { const failed = scenario.checks.some((check) => check.status === "fail"); return <Card key={`${scenario.scenario.underlying_change_percent}-${scenario.scenario.days_forward}`} className="gap-0"><CardHeader className="border-b"><div className="flex items-start justify-between gap-3"><div><CardTitle className="text-base">Stock {scenario.scenario.underlying_change_percent}%</CardTitle><CardDescription>IV +{scenario.scenario.iv_change_percent}% · {scenario.scenario.days_forward} days</CardDescription></div><GateBadge status={failed ? "fail" : "pass"} /></div></CardHeader><CardContent className="space-y-4 pt-4"><dl className="grid gap-px overflow-hidden rounded-lg border bg-border"><SummaryMetric label="Position P&L" value={currency.format(scenario.position_pnl)} tone={scenario.position_pnl < 0 ? "negative" : "positive"} /><SummaryMetric label="Portfolio P&L" value={scenario.portfolio_pnl_percent === null ? "Unknown" : `${scenario.portfolio_pnl_percent.toFixed(2)}%`} tone={scenario.portfolio_pnl_percent !== null && scenario.portfolio_pnl_percent < 0 ? "negative" : "positive"} /><SummaryMetric label="Post-Stress Concentration" value={scenario.post_stress_single_name_percent === null ? "Unknown" : `${scenario.post_stress_single_name_percent.toFixed(2)}%`} /></dl><details className="rounded-md border"><summary className="cursor-pointer px-3 py-2 text-xs font-medium">Policy Gate Arithmetic</summary><div className="space-y-2 border-t p-3">{scenario.checks.map((check) => <div key={check.key} className="text-xs"><div className="flex items-center justify-between gap-2"><strong>{check.label}</strong><GateBadge status={check.status} /></div><code className="mt-1 block overflow-x-auto text-[10px] text-muted-foreground">{check.arithmetic}</code></div>)}</div></details></CardContent></Card> })}</div><Alert><AlertTriangle /><AlertTitle>Model Boundaries</AlertTitle><AlertDescription>{result.limitations.join(" ")}</AlertDescription></Alert></section>
}

function JournalWorkspace({ workspace, selectedExpression, onWorkspaceChange }: { workspace: DecisionCenterWorkspace; selectedExpression: InstrumentExpression | null; onWorkspaceChange: (workspace: DecisionCenterWorkspace) => void }) {
  const [decisionType, setDecisionType] = useState<DecisionType>("ownership")
  const [state, setState] = useState<DecisionState>("planned")
  const [rationale, setRationale] = useState("")
  const [records, setRecords] = useState<DecisionJournalRecord[]>(workspace.decisions)
  const [selectedId, setSelectedId] = useState(workspace.decisions[0]?.decision_id || "")
  const [filters, setFilters] = useState({ ticker: workspace.ticker, state: "", decisionType: "", startDate: "", endDate: "", reviewStatus: "" })
  const [loading, setLoading] = useState(false)

  const selected = records.find((record) => record.decision_id === selectedId) || null

  const create = async () => {
    setLoading(true)
    try {
      const record = await createDecisionRecord({
        ticker: workspace.ticker,
        decision_type: decisionType,
        state,
        thesis_id: workspace.thesis?.thesis_id || null,
        position_intent_id: workspace.position_intent?.intent_id || null,
        expression: selectedExpression || workspace.entry_plans[0]?.expression || null,
        entry_plan_id: workspace.entry_plans[0]?.entry_plan_id || null,
        rationale,
        option_position_id: null,
        actual_execution: {},
      })
      const next = [record, ...records]
      setRecords(next)
      setSelectedId(record.decision_id)
      onWorkspaceChange({ ...workspace, decisions: [record, ...workspace.decisions] })
      toast.success("Decision snapshot added to the journal.")
    } catch (error) {
      toast.error("Decision was not journaled", { description: errorMessage(error) })
    } finally {
      setLoading(false)
    }
  }

  const search = async () => {
    setLoading(true)
    try {
      const result = await loadDecisionRecords({
        ticker: filters.ticker || undefined,
        state: filters.state ? filters.state as DecisionState : undefined,
        decision_type: filters.decisionType ? filters.decisionType as DecisionType : undefined,
        start_date: filters.startDate || undefined,
        end_date: filters.endDate || undefined,
        review_status: filters.reviewStatus ? filters.reviewStatus as "reviewed" | "unreviewed" : undefined,
      })
      setRecords(result)
      setSelectedId(result[0]?.decision_id || "")
    } catch (error) {
      toast.error("Journal search failed", { description: errorMessage(error) })
    } finally {
      setLoading(false)
    }
  }

  const replaceRecord = (record: DecisionJournalRecord) => {
    setRecords((current) => current.map((item) => item.decision_id === record.decision_id ? record : item))
    if (record.ticker === workspace.ticker) onWorkspaceChange({ ...workspace, decisions: workspace.decisions.map((item) => item.decision_id === record.decision_id ? record : item) })
  }

  return <div className="space-y-5"><div className="grid gap-5 xl:grid-cols-[minmax(320px,0.7fr)_minmax(0,1.3fr)]"><Card className="gap-0"><CardHeader className="border-b"><CardTitle>Create Decision Record</CardTitle><CardDescription>Freeze the current thesis, policy, intent, expression, and entry plan into an auditable snapshot.</CardDescription></CardHeader><CardContent className="space-y-4 pt-5"><div className="grid gap-4 sm:grid-cols-2"><Field label="Decision Type"><Select value={decisionType} onValueChange={(value) => setDecisionType(value as DecisionType)}><SelectTrigger aria-label="Decision type"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(decisionTypeLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></Field><Field label="Initial State"><Select value={state} onValueChange={(value) => setState(value as DecisionState)}><SelectTrigger aria-label="Decision state"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(decisionStateLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></Field></div><Field label="Decision Rationale"><Textarea aria-label="Decision rationale" className="min-h-28" value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Why this decision, with this size and expression, now?" /></Field><div className="rounded-lg border bg-muted/10 p-4 text-xs leading-5 text-muted-foreground"><strong className="text-foreground">Snapshot includes:</strong> {workspace.thesis ? `Thesis v${workspace.thesis.version}` : "No thesis"} · {workspace.risk_policy ? `Risk policy v${workspace.risk_policy.version}` : "No risk policy"} · {workspace.position_intent ? `Position intent v${workspace.position_intent.version}` : "No position intent"} · {workspace.entry_plans[0] ? `Entry plan v${workspace.entry_plans[0].version}` : "No entry plan"}</div><Button type="button" disabled={loading} onClick={() => void create()}>{loading ? <LoaderCircle className="motion-safe:animate-spin" /> : <Database />}Create Immutable Snapshot</Button></CardContent></Card>
      <Card className="gap-0"><CardHeader className="border-b"><div className="flex flex-wrap items-center justify-between gap-3"><div><CardTitle>Decision Journal</CardTitle><CardDescription>Filter by company, state, type, date, and review status.</CardDescription></div><Badge variant="outline">{records.length} Records</Badge></div></CardHeader><CardContent className="space-y-4 pt-5"><div className="grid gap-3 md:grid-cols-3"><Field label="Company"><Input aria-label="Journal company filter" value={filters.ticker} onChange={(event) => setFilters((current) => ({ ...current, ticker: event.target.value.toUpperCase() }))} /></Field><Field label="State"><Select value={filters.state || "all"} onValueChange={(value) => setFilters((current) => ({ ...current, state: value === "all" ? "" : value }))}><SelectTrigger aria-label="Journal state filter"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All States</SelectItem>{Object.entries(decisionStateLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></Field><Field label="Type"><Select value={filters.decisionType || "all"} onValueChange={(value) => setFilters((current) => ({ ...current, decisionType: value === "all" ? "" : value }))}><SelectTrigger aria-label="Journal type filter"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All Types</SelectItem>{Object.entries(decisionTypeLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></Field><Field label="From"><Input aria-label="Journal start date" type="date" value={filters.startDate} onChange={(event) => setFilters((current) => ({ ...current, startDate: event.target.value }))} /></Field><Field label="To"><Input aria-label="Journal end date" type="date" value={filters.endDate} onChange={(event) => setFilters((current) => ({ ...current, endDate: event.target.value }))} /></Field><Field label="Review"><Select value={filters.reviewStatus || "all"} onValueChange={(value) => setFilters((current) => ({ ...current, reviewStatus: value === "all" ? "" : value }))}><SelectTrigger aria-label="Journal review filter"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All Reviews</SelectItem><SelectItem value="reviewed">Reviewed</SelectItem><SelectItem value="unreviewed">Unreviewed</SelectItem></SelectContent></Select></Field></div><Button type="button" size="sm" variant="outline" disabled={loading} onClick={() => void search()}><Search />Apply Filters</Button><div className="max-h-80 space-y-2 overflow-y-auto pr-1">{records.length ? records.map((record) => <button key={record.decision_id} type="button" className={cn("w-full rounded-lg border p-3 text-left transition-colors hover:border-primary/50", selectedId === record.decision_id && "border-primary bg-primary/5")} onClick={() => setSelectedId(record.decision_id)}><div className="flex items-center justify-between gap-3"><strong>{record.ticker} · {decisionTypeLabels[record.decision_type as DecisionType] || record.decision_type}</strong><Badge variant="outline">{decisionStateLabels[record.state as DecisionState] || record.state}</Badge></div><p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">{record.rationale || "No rationale recorded."}</p><div className="mt-2 flex justify-between font-mono text-[9px] text-muted-foreground"><span>REV {record.revision}</span><span>{new Date(record.updated_at).toLocaleDateString()}</span></div></button>) : <div className="rounded-lg border border-dashed p-5 text-center text-sm text-muted-foreground">No decisions match these filters.</div>}</div></CardContent></Card></div>{selected ? <DecisionReview record={selected} onSaved={replaceRecord} /> : null}</div>
}

function DecisionReview({ record, onSaved }: { record: DecisionJournalRecord; onSaved: (record: DecisionJournalRecord) => void }) {
  const [state, setState] = useState(record.state as DecisionState)
  const [rationale, setRationale] = useState(record.rationale)
  const [review, setReview] = useState<ProcessReview>(record.process_review)
  const [includeOutcome, setIncludeOutcome] = useState(Boolean(record.later_outcome))
  const [outcome, setOutcome] = useState<LaterOutcome>(record.later_outcome || { as_of: new Date().toISOString().slice(0, 10), outcome: "unavailable", return_percent: null, description: "" })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setState(record.state as DecisionState)
    setRationale(record.rationale)
    setReview(record.process_review)
    setIncludeOutcome(Boolean(record.later_outcome))
    setOutcome(record.later_outcome || { as_of: new Date().toISOString().slice(0, 10), outcome: "unavailable", return_percent: null, description: "" })
  }, [record])

  const save = async (nextState = state) => {
    setSaving(true)
    try {
      const result = await updateDecisionRecord(record.decision_id, {
        state: nextState,
        rationale,
        actual_execution: record.actual_execution,
        process_review: review,
        later_outcome: includeOutcome ? outcome : null,
      })
      onSaved(result)
      toast.success(`Decision revision ${result.revision} saved.`)
    } catch (error) {
      toast.error("Decision review was not saved", { description: errorMessage(error) })
    } finally {
      setSaving(false)
    }
  }

  const reviewField = (label: string, key: keyof Pick<ProcessReview, "thesis_evidence_sufficient" | "position_inside_risk_budget" | "instrument_fit_intended_exposure" | "execution_followed_plan" | "exit_followed_rule">) => <Field label={label}><Select value={review[key]} onValueChange={(value) => setReview((current) => ({ ...current, [key]: value }))}><SelectTrigger aria-label={label}><SelectValue /></SelectTrigger><SelectContent>{["unreviewed", "yes", "no", "not_applicable"].map((value) => <SelectItem key={value} value={value}>{value.replace("_", " ")}</SelectItem>)}</SelectContent></Select></Field>

  return <Card className="gap-0"><CardHeader className="border-b"><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>Process Review · {record.ticker}</CardTitle><CardDescription>Judge decision quality separately from what happened later.</CardDescription></div><div className="flex items-center gap-2"><Badge variant="outline">Revision {record.revision}</Badge>{record.process_outcome_classification ? <Badge variant="secondary">{record.process_outcome_classification.replaceAll("_", " ")}</Badge> : null}</div></div></CardHeader><CardContent className="space-y-6 pt-5"><div className="grid gap-4 lg:grid-cols-[240px_1fr_auto]"><Field label="Decision State"><Select value={state} onValueChange={(value) => setState(value as DecisionState)}><SelectTrigger aria-label="Review decision state"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(decisionStateLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></Field><Field label="Rationale"><Input aria-label="Review rationale" value={rationale} onChange={(event) => setRationale(event.target.value)} /></Field><div className="flex items-end"><Button type="button" variant="outline" disabled={saving || state === "planned"} onClick={() => { setState("planned"); void save("planned") }}><RefreshCw />Reopen As Planned</Button></div></div><div className="grid gap-5 xl:grid-cols-2"><section className="space-y-4 rounded-lg border p-4"><div><h3 className="font-semibold">Process Quality</h3><p className="mt-1 text-xs leading-5 text-muted-foreground">Would the decision still have been sound using only information known at the time?</p></div><div className="grid gap-4 sm:grid-cols-2">{reviewField("Thesis Evidence Sufficient", "thesis_evidence_sufficient")}{reviewField("Inside Risk Budget", "position_inside_risk_budget")}{reviewField("Instrument Fit Intent", "instrument_fit_intended_exposure")}{reviewField("Execution Followed Plan", "execution_followed_plan")}{reviewField("Exit Followed Rule", "exit_followed_rule")}<Field label="Overall Process Quality"><Select value={review.process_quality} onValueChange={(value) => setReview((current) => ({ ...current, process_quality: value as ProcessReview["process_quality"] }))}><SelectTrigger aria-label="Overall process quality"><SelectValue /></SelectTrigger><SelectContent>{["unreviewed", "good", "mixed", "poor"].map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent></Select></Field></div><Field label="Process Notes"><Textarea aria-label="Process review notes" value={review.notes} onChange={(event) => setReview((current) => ({ ...current, notes: event.target.value }))} /></Field></section><section className="space-y-4 rounded-lg border p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold">Later Outcome</h3><p className="mt-1 text-xs leading-5 text-muted-foreground">Optional hindsight record. It never rewrites the earlier snapshot.</p></div><Button type="button" size="sm" variant={includeOutcome ? "default" : "outline"} onClick={() => setIncludeOutcome((current) => !current)}>{includeOutcome ? "Included" : "Add Outcome"}</Button></div>{includeOutcome ? <div className="grid gap-4 sm:grid-cols-2"><Field label="As Of"><Input aria-label="Outcome as of" type="date" value={outcome.as_of} onChange={(event) => setOutcome((current) => ({ ...current, as_of: event.target.value }))} /></Field><Field label="Outcome"><Select value={outcome.outcome} onValueChange={(value) => setOutcome((current) => ({ ...current, outcome: value as LaterOutcome["outcome"] }))}><SelectTrigger aria-label="Later outcome"><SelectValue /></SelectTrigger><SelectContent>{["unavailable", "favorable", "neutral", "unfavorable"].map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent></Select></Field><Field label="Return %"><Input aria-label="Outcome return percent" type="number" step="0.01" value={outcome.return_percent ?? ""} onChange={(event) => setOutcome((current) => ({ ...current, return_percent: optionalNumber(event.target.value) }))} /></Field><Field label="Outcome Description" className="sm:col-span-2"><Textarea aria-label="Outcome description" value={outcome.description} onChange={(event) => setOutcome((current) => ({ ...current, description: event.target.value }))} /></Field></div> : <div className="grid min-h-40 place-items-center rounded-lg border border-dashed p-5 text-center text-sm leading-6 text-muted-foreground">Leave outcome blank when enough time has not passed. An unavailable outcome is different from a poor process.</div>}</section></div><div className="flex flex-wrap items-center justify-between gap-3"><details className="text-xs text-muted-foreground"><summary className="cursor-pointer font-medium text-foreground">Inspect Preserved Snapshots</summary><p className="mt-2">Thesis {record.thesis_snapshot ? `v${record.thesis_snapshot.version}` : "not included"} · Risk policy {record.risk_policy_snapshot ? `v${record.risk_policy_snapshot.version}` : "not included"} · Position intent {record.position_intent_snapshot ? `v${record.position_intent_snapshot.version}` : "not included"} · Entry plan {record.entry_plan_snapshot ? `v${record.entry_plan_snapshot.version}` : "not included"}</p></details><Button type="button" disabled={saving} onClick={() => void save()}>{saving ? <LoaderCircle className="motion-safe:animate-spin" /> : <ClipboardCheck />}Save Review Revision</Button></div></CardContent></Card>
}

export function DecisionCenter({ initialTicker = "NVDA" }: { initialTicker?: string }) {
  const [ticker, setTicker] = useState(normalizeTicker(initialTicker))
  const [tickerInput, setTickerInput] = useState(normalizeTicker(initialTicker))
  const [workspace, setWorkspace] = useState<DecisionCenterWorkspace | null>(null)
  const [selectedExpression, setSelectedExpression] = useState<InstrumentExpression | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const load = useCallback(async (symbol: string) => {
    const normalized = normalizeTicker(symbol)
    setLoading(true)
    try {
      const result = await loadDecisionCenter(normalized)
      setWorkspace(result)
      setTicker(result.ticker)
      setTickerInput(result.ticker)
      setSelectedExpression(result.entry_plans[0]?.expression || null)
      setError("")
      window.history.replaceState(null, "", labHref("decision", result.ticker))
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load(ticker) }, [load, ticker])

  const submitTicker = (event: FormEvent) => {
    event.preventDefault()
    const normalized = normalizeTicker(tickerInput)
    if (normalized === ticker) void load(normalized)
    else setTicker(normalized)
  }

  const readiness = useMemo(() => {
    if (!workspace) return { label: "Loading", tone: "outline" as const }
    if (workspace.thesis?.status === "invalidated") return { label: "Thesis Invalidated", tone: "destructive" as const }
    if (!workspace.thesis || !workspace.position_intent || !workspace.risk_policy) return { label: "Context Incomplete", tone: "outline" as const }
    return { label: "Planning Context Ready", tone: "secondary" as const }
  }, [workspace])

  return <div className="min-h-screen">
    <header className="sticky top-0 z-30 border-b bg-background/92 px-3 py-3 shadow-sm backdrop-blur sm:px-5 xl:px-8"><div className="mx-auto flex max-w-[1720px] flex-wrap items-center gap-3"><form className="flex items-center gap-2" onSubmit={submitTicker}><Input aria-label="Decision Center ticker" className="w-28 font-mono font-semibold uppercase" maxLength={12} value={tickerInput} onChange={(event) => setTickerInput(event.target.value.toUpperCase())} /><Button type="submit" variant="outline" disabled={loading}><Search />Open Company</Button></form><div className="ml-0 flex flex-1 flex-wrap items-center justify-end gap-2"><Badge variant={readiness.tone}>{readiness.label}</Badge>{workspace?.risk_policy ? <Badge variant="outline"><ShieldAlert />Policy v{workspace.risk_policy.version}</Badge> : null}<Button asChild size="sm" variant="ghost"><a href={labHref("intelligence", ticker)}>Evidence<ExternalLink /></a></Button><Button asChild size="sm" variant="ghost"><a href={labHref("options", ticker)}>Option Lab<ExternalLink /></a></Button></div></div></header>
    <div className="mx-auto max-w-[1720px] space-y-6 px-3 py-6 sm:px-5 xl:px-8"><section className="overflow-hidden rounded-xl border bg-[linear-gradient(120deg,rgba(182,245,89,0.08),transparent_42%),var(--card)] p-5 sm:p-7"><div className="flex flex-wrap items-start justify-between gap-5"><div className="max-w-3xl"><div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-primary"><NotebookTabs className="size-4" />Decision Research Record</div><h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">{workspace?.company_name || ticker}</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">Move from evidence to position intent, instrument fit, staged entry, stress gates, and process review—without turning research into a recommendation or order ticket.</p></div>{workspace ? <dl className="grid min-w-[280px] gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-2"><SummaryMetric label="Company" value={workspace.ticker} /><SummaryMetric label="Journal" value={`${workspace.decisions.length} decisions`} /></dl> : null}</div><div className="mt-6"><DecisionChain workspace={workspace} /></div></section>
      {error ? <Alert variant="destructive"><AlertTriangle /><AlertTitle>Decision Context Unavailable</AlertTitle><AlertDescription><p>{error}</p><Button className="mt-3" size="sm" variant="outline" onClick={() => void load(ticker)}><RefreshCw />Try Again</Button></AlertDescription></Alert> : null}
      {loading ? <div className="grid min-h-[420px] place-items-center rounded-xl border border-dashed text-sm text-muted-foreground"><div><LoaderCircle className="mr-2 inline size-4 motion-safe:animate-spin" />Loading local decision context…</div></div> : workspace ? <Tabs defaultValue="thesis" className="space-y-5"><TabsList className="h-auto w-full justify-start overflow-x-auto bg-card p-1"><TabsTrigger value="thesis"><FileText />Thesis</TabsTrigger><TabsTrigger value="position"><WalletCards />Position &amp; Fit</TabsTrigger><TabsTrigger value="entry"><Target />Entry &amp; Stress</TabsTrigger><TabsTrigger value="journal"><History />Journal</TabsTrigger></TabsList><TabsContent value="thesis"><ThesisWorkspace key={`thesis-${workspace.thesis?.thesis_id || "new"}`} workspace={workspace} onSaved={setWorkspace} /></TabsContent><TabsContent value="position"><PositionAndExpressionWorkspace key={`position-${workspace.position_intent?.intent_id || "new"}`} workspace={workspace} onWorkspaceChange={setWorkspace} selectedExpression={selectedExpression} onSelectExpression={setSelectedExpression} /></TabsContent><TabsContent value="entry"><EntryAndStressWorkspace key={`entry-${workspace.entry_plans[0]?.entry_plan_id || selectedExpression?.name || "new"}`} workspace={workspace} selectedExpression={selectedExpression} onWorkspaceChange={setWorkspace} /></TabsContent><TabsContent value="journal"><JournalWorkspace key={`journal-${workspace.decisions[0]?.decision_id || "new"}`} workspace={workspace} selectedExpression={selectedExpression} onWorkspaceChange={setWorkspace} /></TabsContent></Tabs> : null}
      <footer className="flex flex-wrap items-center justify-between gap-3 border-t py-4 text-xs text-muted-foreground"><span>Local-only educational research. No live orders or automatic thesis promotion.</span><span className="font-mono">DRC-02 — DRC-06</span></footer>
    </div>
  </div>
}
