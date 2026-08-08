import { useCallback, useEffect, useState } from "react"
import { AlertCircle, Columns2, Database, Keyboard, Rows2 } from "lucide-react"
import { toast } from "sonner"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable"
import { EvidenceWorkspace } from "@/features/strategy-lab/evidence-workspace"
import { MarketWorkspaceChart } from "@/features/strategy-lab/market-workspace-chart"
import { ProposalReviewDialog } from "@/features/strategy-lab/proposal-review-dialog"
import { ResearchContextBar } from "@/features/strategy-lab/research-context-bar"
import { StrategyCommand } from "@/features/strategy-lab/strategy-command"
import { StrategyComposer } from "@/features/strategy-lab/strategy-composer"
import { selectedResearchDesign, selectedSearchRanges, useResearchWorkspace } from "@/features/strategy-lab/workspace"
import {
  ApiError,
  createParameterSearch,
  createResearchRun,
  loadChartData,
  loadStrategySources,
  proposeInstruction,
  runCatalogueStrategy,
  runInstruction,
  saveStrategy,
} from "@/lib/api"
import type { CatalogueStrategy, DataStatus, LegacyProposal, PricePoint, StrategyTemplate } from "@/lib/types"

function errorMessage(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return "The research request failed unexpectedly."
}

export function preferredScrollBehavior(): ScrollBehavior {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"
}

function useWideCanvas() {
  const [wide, setWide] = useState(false)
  useEffect(() => {
    const query = window.matchMedia("(min-width: 1100px)")
    const update = () => setWide(query.matches)
    update()
    query.addEventListener("change", update)
    return () => query.removeEventListener("change", update)
  }, [])
  return wide
}

function CanvasPanels({ templates, openCommand, preview, previewLoading }: {
  templates: StrategyTemplate[]
  openCommand: () => void
  preview: PricePoint[]
  previewLoading: boolean
}) {
  const { state } = useResearchWorkspace()
  const wide = useWideCanvas()
  const [layout, setLayout] = useState<"split" | "stacked">(() => {
    try {
      return window.localStorage.getItem("gbb.strategyLab.canvasLayout") === "stacked" ? "stacked" : "split"
    } catch {
      return "split"
    }
  })
  const template = state.selection.kind === "template" ? state.selection.template : undefined
  const parameterValues = state.selection.kind === "template" ? state.selection.instance.parameter_values : undefined
  const chart = <MarketWorkspaceChart points={preview} marketChart={state.result?.marketChart} trades={state.result?.trades} template={template} parameterValues={parameterValues} loading={previewLoading} symbol={state.ticker} />
  const chooseLayout = (nextLayout: "split" | "stacked") => {
    setLayout(nextLayout)
    try {
      window.localStorage.setItem("gbb.strategyLab.canvasLayout", nextLayout)
    } catch {
      return
    }
  }
  const toolbar = wide && <div className="flex items-center justify-between border-b bg-card/70 px-3 py-2"><span className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Canvas Layout</span><div className="flex items-center gap-1"><Button size="sm" variant={layout === "split" ? "secondary" : "ghost"} aria-pressed={layout === "split"} onClick={() => chooseLayout("split")}><Columns2 />Side By Side</Button><Button size="sm" variant={layout === "stacked" ? "secondary" : "ghost"} aria-pressed={layout === "stacked"} onClick={() => chooseLayout("stacked")}><Rows2 />Stacked</Button></div></div>
  if (!wide || layout === "stacked") return <div className="overflow-hidden rounded-lg border">{toolbar}<div className="min-h-[420px] border-b"><StrategyComposer templates={templates} onOpenCommand={openCommand} /></div>{chart}</div>
  return <div className="overflow-hidden rounded-lg border">{toolbar}<div className="h-[735px]"><ResizablePanelGroup id="strategy-research-canvas" orientation="horizontal"><ResizablePanel id="strategy-composer-panel" defaultSize="36%" minSize="24%" maxSize="68%"><StrategyComposer templates={templates} onOpenCommand={openCommand} /></ResizablePanel><ResizableHandle withHandle /><ResizablePanel id="strategy-chart-panel" defaultSize="64%" minSize="32%">{chart}</ResizablePanel></ResizablePanelGroup></div></div>
}

export function StrategyLab() {
  const { state, dispatch } = useResearchWorkspace()
  const [templates, setTemplates] = useState<StrategyTemplate[]>([])
  const [catalogue, setCatalogue] = useState<CatalogueStrategy[]>([])
  const [sourcesError, setSourcesError] = useState("")
  const [commandOpen, setCommandOpen] = useState(false)
  const [running, setRunning] = useState(false)
  const [proposal, setProposal] = useState<LegacyProposal | null>(null)
  const [proposalInstruction, setProposalInstruction] = useState("")
  const [proposalOpen, setProposalOpen] = useState(false)
  const [preview, setPreview] = useState<PricePoint[]>([])
  const [previewStatus, setPreviewStatus] = useState<DataStatus>({})
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState("")

  const refreshSources = useCallback(async () => {
    try {
      const sources = await loadStrategySources()
      setTemplates(sources.templates)
      setCatalogue(sources.catalogue)
      setSourcesError("")
    } catch (error) {
      setSourcesError(errorMessage(error))
    }
  }, [])

  useEffect(() => { void refreshSources() }, [refreshSources])
  useEffect(() => {
    const open = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        setCommandOpen(true)
      }
    }
    window.addEventListener("keydown", open)
    return () => window.removeEventListener("keydown", open)
  }, [])

  const portfolio = state.selection.kind === "template" && state.selection.template.rule_graph.kind === "ranked_portfolio"
  useEffect(() => {
    if (portfolio || !state.ticker.trim()) {
      setPreview([])
      setPreviewError("")
      return
    }
    let active = true
    const timer = window.setTimeout(async () => {
      setPreviewLoading(true)
      try {
        const payload = await loadChartData(state.ticker.trim().toUpperCase(), state.timeframe, ["sma_20", "ema_20", "rsi_14", "volume_sma_20"])
        if (!active) return
        setPreview(payload.chart)
        setPreviewStatus(payload.dataStatus)
        setPreviewError("")
      } catch (error) {
        if (!active) return
        setPreview([])
        setPreviewError(errorMessage(error))
      } finally {
        if (active) setPreviewLoading(false)
      }
    }, 250)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [portfolio, state.ticker, state.timeframe])

  const runSelected = async () => {
    if (state.selection.kind === "none") return setCommandOpen(true)
    if (!portfolio && !state.ticker.trim()) return toast.error("Choose a US ticker before running research.")
    if (state.selection.kind === "instruction") {
      const instruction = state.selection.instruction.trim()
      if (instruction.length < 8) return toast.error("Describe the entry and exit idea in at least eight characters.")
      setRunning(true)
      try {
        const nextProposal = await proposeInstruction(instruction)
        setProposal(nextProposal)
        setProposalInstruction(instruction)
        setProposalOpen(true)
      } catch (error) {
        toast.error("Strategy translation failed", { description: errorMessage(error) })
      } finally {
        setRunning(false)
      }
      return
    }

    setRunning(true)
    try {
      if (state.selection.kind === "catalogue") {
        const result = await runCatalogueStrategy(state.ticker, state.selection.strategy.id, state.timeframe, state.benchmark, state.commissionBps, state.slippageBps)
        dispatch({ type: "set-result", result, label: `Catalogue · ${state.selection.strategy.name}` })
      } else {
        await saveStrategy(state.selection.instance, state.selection.instance.description)
        const design = selectedResearchDesign(state)
        const ranges = selectedSearchRanges(state)
        if (Object.keys(ranges).length) {
          const search = await createParameterSearch(state.selection.instance, design, state.validation, ranges)
          dispatch({ type: "set-result", result: search.finalTest, search, label: `${search.method} · Untouched Final Test` })
        } else {
          const run = await createResearchRun(state.selection.instance, design, state.validation)
          dispatch({ type: "set-result", result: run.results, label: `Single Configuration · ${state.timeframe}` })
        }
      }
      toast.success("Research evidence is ready.")
      void refreshSources()
      window.setTimeout(() => document.getElementById("evidence-workspace")?.scrollIntoView({ behavior: preferredScrollBehavior(), block: "start" }), 100)
    } catch (error) {
      toast.error("Research run failed", { description: errorMessage(error) })
    } finally {
      setRunning(false)
    }
  }

  const confirmProposal = async () => {
    if (!proposal) return
    setRunning(true)
    try {
      const result = proposal.existingStrategy
        ? await runCatalogueStrategy(state.ticker, proposal.existingStrategy.id, state.timeframe, state.benchmark, state.commissionBps, state.slippageBps)
        : await runInstruction(state.ticker, proposalInstruction, proposal.strategyYaml, state.timeframe, state.benchmark, state.commissionBps, state.slippageBps)
      dispatch({ type: "set-result", result, label: `Confirmed Translation · ${proposal.strategy.name}` })
      setProposalOpen(false)
      toast.success("Translated strategy completed its research run.")
      void refreshSources()
    } catch (error) {
      toast.error("Research run failed", { description: errorMessage(error) })
    } finally {
      setRunning(false)
    }
  }

  const sourceLabel = [previewStatus.source || "Yahoo Finance", previewStatus.status].filter(Boolean).join(" · ")
  const stalePreview = previewStatus.status?.toLowerCase().includes("stale")
  return <>
    <ResearchContextBar running={running} onRun={() => void runSelected()} onOpenCommand={() => setCommandOpen(true)} />
    <div className="space-y-4 p-3 sm:p-4 xl:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3 px-1"><div><div className="mb-2 flex items-center gap-2"><Badge variant="outline" className="border-primary/30 text-primary">Research Canvas</Badge><Badge variant="secondary">Local First</Badge></div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Turn a market idea into inspectable evidence.</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">Compose in plain language or edit a validated rule directly beside its market behavior. Advanced assumptions stay available without becoming the product.</p></div><div className="flex items-center gap-2 text-xs text-muted-foreground"><Keyboard className="size-4" /><span><kbd className="rounded border px-1.5 py-0.5 font-mono">⌘ K</kbd> strategy search</span></div></div>
      {sourcesError && <Alert variant="destructive"><AlertCircle /><AlertTitle>Strategy Sources Unavailable</AlertTitle><AlertDescription>{sourcesError}</AlertDescription></Alert>}
      {previewError && <Alert variant="destructive"><AlertCircle /><AlertTitle>Market Preview Unavailable</AlertTitle><AlertDescription>{previewError}</AlertDescription></Alert>}
      {stalePreview ? <Alert variant="destructive"><Database /><AlertTitle>Serving Stale Local Data</AlertTitle><AlertDescription>{previewStatus.qualityWarnings?.join(" ") || "The live provider is unavailable, so the newest local observation is displayed."}</AlertDescription></Alert> : previewStatus.observationTimestamp ? <div className="flex flex-wrap items-center gap-2 px-1 font-mono text-[10px] text-muted-foreground"><Database className="size-3" /><span>{sourceLabel}</span><span>·</span><span>Observed {new Date(previewStatus.observationTimestamp).toLocaleDateString()}</span></div> : null}
      <CanvasPanels templates={templates} openCommand={() => setCommandOpen(true)} preview={preview} previewLoading={previewLoading} />
      <section id="evidence-workspace" className="scroll-mt-20 overflow-hidden rounded-lg border"><EvidenceWorkspace result={state.result} search={state.search} runLabel={state.runLabel} /></section>
    </div>
    <StrategyCommand open={commandOpen} onOpenChange={setCommandOpen} templates={templates} catalogue={catalogue} />
    <ProposalReviewDialog proposal={proposal} open={proposalOpen} running={running} onOpenChange={setProposalOpen} onConfirm={() => void confirmProposal()} />
  </>
}
