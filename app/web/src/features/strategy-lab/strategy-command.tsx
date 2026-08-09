import { Bookmark, Library, Sparkles } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator } from "@/components/ui/command"
import type { CatalogueStrategy, StrategyTemplate } from "@/lib/types"
import { useResearchWorkspace } from "@/features/strategy-lab/workspace"

interface StrategyCommandProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  templates: StrategyTemplate[]
  catalogue: CatalogueStrategy[]
}

export function StrategyCommand({ open, onOpenChange, templates, catalogue }: StrategyCommandProps) {
  const { dispatch } = useResearchWorkspace()
  const chooseTemplate = (template: StrategyTemplate) => {
    dispatch({ type: "select-template", template })
    onOpenChange(false)
  }
  const chooseCatalogue = (strategy: CatalogueStrategy) => {
    dispatch({ type: "select-catalogue", strategy, template: templates.find((template) => template.template_id === strategy.strategyJson?.template_id) })
    onOpenChange(false)
  }
  const families = [...new Set(templates.map((template) => template.family))]
  return (
    <CommandDialog open={open} onOpenChange={onOpenChange} title="Choose a strategy" description="Search validated templates and saved local strategies" className="max-w-2xl border-border bg-popover">
      <CommandInput placeholder="Search templates, families, or saved strategies…" />
      <CommandList className="max-h-[520px]">
        <CommandEmpty>No matching strategy found.</CommandEmpty>
        {catalogue.length > 0 && <CommandGroup heading="Recent Catalogue"><>{catalogue.slice(0, 8).map((strategy) => <CommandItem key={strategy.id} value={`saved ${strategy.name} ${strategy.description} ${strategy.family || ""}`} onSelect={() => chooseCatalogue(strategy)} className="py-3"><Bookmark className="text-primary" /><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><span>{strategy.name}</span><Badge variant="outline" className="text-[9px]">Saved</Badge></div><p className="mt-1 truncate text-xs text-muted-foreground">{strategy.description}</p></div></CommandItem>)}</></CommandGroup>}
        <CommandSeparator />
        {families.map((family) => <CommandGroup key={family} heading={family}><>{templates.filter((template) => template.family === family).map((template) => <CommandItem key={template.template_id} value={`${template.name} ${template.description} ${template.family}`} onSelect={() => chooseTemplate(template)} className="py-3"><Library className="text-muted-foreground" /><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><span>{template.name}</span><Badge variant="secondary" className="text-[9px]">Validated</Badge><Badge variant="outline" className="text-[9px]">{template.rule_graph.kind === "ranked_portfolio" ? "Portfolio" : "Single Stock"}</Badge></div><p className="mt-1 truncate text-xs text-muted-foreground">{template.description}</p></div></CommandItem>)}</></CommandGroup>)}
        <CommandSeparator />
        <CommandGroup heading="Natural Language"><CommandItem value="natural language custom strategy instruction" onSelect={() => { dispatch({ type: "edit-instruction", instruction: "" }); onOpenChange(false) }} className="py-3"><Sparkles className="text-primary" /><div><span>Start From An Instruction</span><p className="mt-1 text-xs text-muted-foreground">Use the configured LLM provider with confirmation before execution.</p></div></CommandItem></CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}
