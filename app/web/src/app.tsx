import { AppShell } from "@/components/app-shell"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { StrategyLab } from "@/features/strategy-lab/strategy-lab"
import { ResearchWorkspaceProvider } from "@/features/strategy-lab/workspace"

export function App() {
  return <TooltipProvider><ResearchWorkspaceProvider><AppShell><StrategyLab /></AppShell><Toaster position="bottom-right" richColors /></ResearchWorkspaceProvider></TooltipProvider>
}
