import { lazy, Suspense } from "react"

import { AppShell } from "@/components/app-shell"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { ResearchWorkspaceProvider } from "@/features/strategy-lab/workspace"

const OptionLab = lazy(() => import("@/features/option-lab/option-lab").then((module) => ({ default: module.OptionLab })))
const StrategyLab = lazy(() => import("@/features/strategy-lab/strategy-lab").then((module) => ({ default: module.StrategyLab })))

export function App() {
  const activeLab = new URLSearchParams(window.location.search).get("lab") === "options" ? "options" : "strategy"
  return <TooltipProvider><AppShell activeLab={activeLab}><Suspense fallback={<div className="grid min-h-screen place-items-center font-mono text-xs text-muted-foreground">Loading research canvas…</div>}>{activeLab === "options" ? <OptionLab /> : <ResearchWorkspaceProvider><StrategyLab /></ResearchWorkspaceProvider>}</Suspense></AppShell><Toaster position="bottom-right" richColors /></TooltipProvider>
}
