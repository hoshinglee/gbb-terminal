import { lazy, Suspense, useEffect } from "react"

import { AppShell } from "@/components/app-shell"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { ResearchWorkspaceProvider } from "@/features/strategy-lab/workspace"
import { labFromSearch, legacyStockRedirect, tickerFromSearch } from "@/lib/navigation"

const MarketPulse = lazy(() => import("@/features/market-pulse/market-pulse").then((module) => ({ default: module.MarketPulse })))
const OptionLab = lazy(() => import("@/features/option-lab/option-lab").then((module) => ({ default: module.OptionLab })))
const StrategyLab = lazy(() => import("@/features/strategy-lab/strategy-lab").then((module) => ({ default: module.StrategyLab })))
const CompanyIntelligence = lazy(() => import("@/features/company-intelligence/company-intelligence").then((module) => ({ default: module.CompanyIntelligence })))
const DecisionCenter = lazy(() => import("@/features/decision-center/decision-center").then((module) => ({ default: module.DecisionCenter })))

export function App() {
  const activeLab = labFromSearch(window.location.search)
  const initialTicker = tickerFromSearch(window.location.search)
  useEffect(() => {
    const destination = legacyStockRedirect(window.location.search)
    if (destination) window.history.replaceState(null, "", destination)
  }, [])
  const canvas = activeLab === "intelligence"
    ? <CompanyIntelligence initialTicker={initialTicker} />
    : activeLab === "decision"
    ? <DecisionCenter initialTicker={initialTicker} />
    : activeLab === "options"
    ? <OptionLab initialTicker={initialTicker} />
    : activeLab === "market"
        ? <MarketPulse />
        : <ResearchWorkspaceProvider initialTicker={initialTicker}><StrategyLab /></ResearchWorkspaceProvider>
  return <TooltipProvider><AppShell activeLab={activeLab}><Suspense fallback={<div className="grid min-h-screen place-items-center font-mono text-xs text-muted-foreground">Loading research canvas…</div>}>{canvas}</Suspense></AppShell><Toaster position="bottom-right" richColors /></TooltipProvider>
}
