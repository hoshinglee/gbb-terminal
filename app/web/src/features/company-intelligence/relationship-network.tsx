import { useMemo, useState } from "react"
import {
  ArrowDownLeft,
  ArrowLeftRight,
  ArrowUpRight,
  ExternalLink,
  Network,
  Radar,
  TableProperties,
} from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { SourceEvidenceDialog } from "@/features/company-intelligence/source-evidence-dialog"
import { loadCompanyRelationshipHistory } from "@/lib/api"
import { labHref } from "@/lib/navigation"
import type {
  CompanyReference,
  CompanyRelationship,
  RelationshipConfidence,
  RelationshipDirection,
  RelationshipHistoryResponse,
  RelationshipNetworkResponse,
  RelationshipType,
} from "@/lib/types"

type DirectionFilter = "all" | RelationshipDirection
type TypeFilter = "all" | RelationshipType
type ConfidenceFilter = "all" | RelationshipConfidence

const directionLabels: Record<RelationshipDirection, string> = {
  upstream: "Upstream",
  downstream: "Downstream",
  bidirectional: "Two-Way",
  market: "Market",
}

const typeLabels: Record<RelationshipType, string> = {
  supplier: "Supplier",
  customer: "Customer",
  manufacturer_foundry: "Manufacturer / Foundry",
  distributor: "Distributor",
  strategic_partner: "Strategic Partner",
  competitor: "Explicit Competitor",
  customer_concentration: "Customer Concentration",
  supplier_concentration: "Supplier Concentration",
}

const confidenceLabels: Record<RelationshipConfidence, string> = {
  disclosed: "Disclosed",
  strongly_inferred: "Strongly Inferred",
  inferred: "Inferred",
}

function counterpart(record: CompanyRelationship, centerId: string): { name: string; company: CompanyReference | null } {
  if (record.sourceCompany.companyId !== centerId) {
    return { name: record.sourceCompany.legalName, company: record.sourceCompany }
  }
  return {
    name: record.targetCompany?.legalName || record.edge.rawCounterpartyName,
    company: record.targetCompany,
  }
}

function exposure(record: CompanyRelationship) {
  if (record.observation.exposureValue === null) return "Not disclosed"
  return `${record.observation.exposureValue.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${record.observation.exposureUnit || ""}`.trim()
}

function readableDate(value: string | null) {
  if (!value) return "Open"
  const parsed = new Date(value.length === 10 ? `${value}T12:00:00` : value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString()
}

function graphPositions(records: CompanyRelationship[]) {
  const groups = new Map<RelationshipDirection, CompanyRelationship[]>([
    ["upstream", []],
    ["downstream", []],
    ["bidirectional", []],
    ["market", []],
  ])
  records.forEach((record) => groups.get(record.perspectiveDirection)?.push(record))
  const positions = new Map<string, { x: number; y: number }>()
  groups.forEach((items, direction) => {
    items.forEach((record, index) => {
      const offset = (index - (items.length - 1) / 2) * Math.min(80, 300 / Math.max(items.length, 1))
      if (direction === "upstream") positions.set(record.edge.relationshipId, { x: 105, y: 220 + offset })
      if (direction === "downstream") positions.set(record.edge.relationshipId, { x: 615, y: 220 + offset })
      if (direction === "bidirectional") positions.set(record.edge.relationshipId, { x: 360 + offset, y: 65 })
      if (direction === "market") positions.set(record.edge.relationshipId, { x: 360 + offset, y: 375 })
    })
  })
  return positions
}

export function RelationshipNetwork({ network, ticker }: { network: RelationshipNetworkResponse | null; ticker: string }) {
  const [direction, setDirection] = useState<DirectionFilter>("all")
  const [relationshipType, setRelationshipType] = useState<TypeFilter>("all")
  const [confidence, setConfidence] = useState<ConfidenceFilter>("all")
  const [selected, setSelected] = useState<CompanyRelationship | null>(null)
  const [history, setHistory] = useState<RelationshipHistoryResponse | null>(null)
  const [historyError, setHistoryError] = useState("")
  const [historyLoading, setHistoryLoading] = useState(false)

  const filtered = useMemo(
    () => (network?.relationships || []).filter((record) => (
      (direction === "all" || record.perspectiveDirection === direction)
      && (relationshipType === "all" || record.edge.relationshipType === relationshipType)
      && (confidence === "all" || record.observation.confidence === confidence)
    )),
    [confidence, direction, network, relationshipType],
  )
  const visualRecords = filtered.slice(0, 16)
  const positions = useMemo(() => graphPositions(visualRecords), [visualRecords])
  const centerCompanyId = network?.company.companyId || ""
  const selectedParty = selected ? counterpart(selected, centerCompanyId) : null

  const inspect = async (record: CompanyRelationship) => {
    setSelected(record)
    setHistory(null)
    setHistoryError("")
    setHistoryLoading(true)
    try {
      setHistory(await loadCompanyRelationshipHistory(ticker, record.edge.relationshipId))
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : "Relationship history is unavailable.")
    } finally {
      setHistoryLoading(false)
    }
  }

  return <div className="space-y-4">
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Evidence-Backed Business Network</CardTitle>
            <CardDescription className="mt-2">One-hop research navigation built only from persisted, source-backed relationships.</CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">As of {network ? new Date(network.asOf).toLocaleString() : "unavailable"}</Badge>
            <Badge variant="outline">{filtered.length} of {network?.matchingRelationshipCount || 0} edges</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <ToggleGroup
            type="single"
            variant="outline"
            value={direction}
            onValueChange={(value) => value && setDirection(value as DirectionFilter)}
            aria-label="Relationship direction"
            className="flex-wrap"
          >
            <ToggleGroupItem value="all">All</ToggleGroupItem>
            <ToggleGroupItem value="upstream"><ArrowUpRight />Upstream</ToggleGroupItem>
            <ToggleGroupItem value="downstream"><ArrowDownLeft />Downstream</ToggleGroupItem>
            <ToggleGroupItem value="bidirectional"><ArrowLeftRight />Two-Way</ToggleGroupItem>
            <ToggleGroupItem value="market"><Radar />Market</ToggleGroupItem>
          </ToggleGroup>
          <Select value={relationshipType} onValueChange={(value) => setRelationshipType(value as TypeFilter)}>
            <SelectTrigger aria-label="Relationship type" className="w-56"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Relationship Types</SelectItem>
              {Object.entries(typeLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={confidence} onValueChange={(value) => setConfidence(value as ConfidenceFilter)}>
            <SelectTrigger aria-label="Relationship confidence" className="w-48"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Confidence Levels</SelectItem>
              {Object.entries(confidenceLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        {visualRecords.length ? <div className="overflow-x-auto rounded-lg border bg-[radial-gradient(circle_at_center,rgba(163,230,53,0.08),transparent_45%)]">
          <svg
            role="img"
            aria-labelledby="business-network-title business-network-description"
            viewBox="0 0 720 440"
            className="min-h-[360px] min-w-[640px] w-full"
          >
            <title id="business-network-title">{ticker} business relationship network</title>
            <desc id="business-network-description">A one-hop view of persisted upstream, downstream, partner, and market relationships. The table following the graph provides the same evidence access.</desc>
            {visualRecords.map((record) => {
              const position = positions.get(record.edge.relationshipId)
              if (!position) return null
              const party = counterpart(record, centerCompanyId)
              return <g key={`edge-${record.edge.relationshipId}`}>
                <line x1="360" y1="220" x2={position.x} y2={position.y} className="stroke-border" strokeWidth="2" strokeDasharray={record.observation.confidence === "disclosed" ? undefined : "6 5"} />
                <line
                  x1="360"
                  y1="220"
                  x2={position.x}
                  y2={position.y}
                  stroke="transparent"
                  strokeWidth="18"
                  className="cursor-pointer"
                  onClick={() => void inspect(record)}
                />
                <text x={(360 + position.x) / 2} y={(220 + position.y) / 2 - 7} textAnchor="middle" className="fill-muted-foreground text-[9px]">{record.observation.exposureValue === null ? typeLabels[record.edge.relationshipType] : exposure(record)}</text>
              </g>
            })}
            <g>
              <circle cx="360" cy="220" r="54" className="fill-primary/15 stroke-primary" strokeWidth="2" />
              <text x="360" y="215" textAnchor="middle" className="fill-foreground text-[15px] font-semibold">{ticker}</text>
              <text x="360" y="235" textAnchor="middle" className="fill-muted-foreground text-[9px]">Selected Company</text>
            </g>
            {visualRecords.map((record) => {
              const position = positions.get(record.edge.relationshipId)
              if (!position) return null
              const party = counterpart(record, centerCompanyId)
              const content = <g className="cursor-pointer">
                <rect x={position.x - 72} y={position.y - 28} width="144" height="56" rx="10" className={party.company ? "fill-card stroke-border" : "fill-muted/30 stroke-muted-foreground"} strokeDasharray={party.company ? undefined : "5 4"} />
                <text x={position.x} y={position.y - 3} textAnchor="middle" className="fill-foreground text-[10px] font-medium">{party.name.length > 22 ? `${party.name.slice(0, 21)}…` : party.name}</text>
                <text x={position.x} y={position.y + 13} textAnchor="middle" className="fill-muted-foreground text-[8px]">{directionLabels[record.perspectiveDirection]} · {confidenceLabels[record.observation.confidence]}</text>
              </g>
              return party.company?.primaryTicker
                ? <a key={`node-${record.edge.relationshipId}`} href={labHref("intelligence", party.company.primaryTicker)} aria-label={`Open ${party.name} Company Intelligence`}>{content}</a>
                : <foreignObject
                    key={`node-${record.edge.relationshipId}`}
                    x={position.x - 72}
                    y={position.y - 28}
                    width="144"
                    height="56"
                  ><button type="button" className="h-full w-full cursor-pointer rounded-[10px] border border-dashed border-muted-foreground bg-muted/30 px-2 text-center" aria-label={`Inspect unresolved counterparty ${party.name}`} onClick={() => void inspect(record)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); void inspect(record) } }}><span className="block truncate text-[10px] font-medium text-foreground">{party.name}</span><span className="mt-1 block text-[8px] text-muted-foreground">{directionLabels[record.perspectiveDirection]} · {confidenceLabels[record.observation.confidence]}</span></button></foreignObject>
            })}
          </svg>
        </div> : <div className="grid min-h-64 place-items-center rounded-lg border border-dashed text-center">
          <div><Network className="mx-auto size-8 text-muted-foreground" /><h3 className="mt-3 font-semibold">No relationships match these filters.</h3><p className="mt-2 max-w-md text-sm text-muted-foreground">Public disclosure is incomplete. An empty network does not prove the company has no suppliers, customers, or partners.</p></div>
        </div>}

        {filtered.length > visualRecords.length ? <Alert><Network /><AlertTitle>Graph Simplified</AlertTitle><AlertDescription>The graph shows the first {visualRecords.length} filtered edges to avoid an unreadable hairball. The complete keyboard-accessible table remains below.</AlertDescription></Alert> : null}
      </CardContent>
    </Card>

    <Card className="gap-0 overflow-hidden py-0">
      <CardHeader className="border-b py-5"><div className="flex items-center gap-2"><TableProperties className="size-4 text-primary" /><CardTitle className="text-base">Relationship Evidence Table</CardTitle></div><CardDescription>Every displayed row has inspectable evidence. Unresolved names are intentionally not linked to a public company.</CardDescription></CardHeader>
      <div className="overflow-x-auto"><Table>
        <TableHeader><TableRow><TableHead>Direction</TableHead><TableHead>Counterparty</TableHead><TableHead>Relationship</TableHead><TableHead>Exposure</TableHead><TableHead>Confidence</TableHead><TableHead>Known / Valid</TableHead><TableHead>Evidence</TableHead></TableRow></TableHeader>
        <TableBody>{filtered.map((record) => {
          const party = counterpart(record, centerCompanyId)
          return <TableRow key={record.edge.relationshipId}>
            <TableCell><Badge variant="outline">{directionLabels[record.perspectiveDirection]}</Badge></TableCell>
            <TableCell><strong className="block min-w-40">{party.name}</strong><span className="text-[10px] text-muted-foreground">{party.company?.primaryTicker || "Unresolved public-company mapping"}</span></TableCell>
            <TableCell>{typeLabels[record.edge.relationshipType]}</TableCell>
            <TableCell>{exposure(record)}</TableCell>
            <TableCell><Badge variant={record.observation.confidence === "disclosed" ? "secondary" : "outline"}>{confidenceLabels[record.observation.confidence]}</Badge><span className="mt-1 block text-[10px] text-muted-foreground">{record.observation.extractionMethod}</span></TableCell>
            <TableCell className="font-mono text-[10px]"><span className="block">Known {new Date(record.observation.knownAt).toLocaleString()}</span><span className="block text-muted-foreground">{readableDate(record.observation.validFrom)} → {readableDate(record.observation.validTo)}</span></TableCell>
            <TableCell><div className="flex flex-wrap gap-2"><SourceEvidenceDialog evidence={record.evidence} label="Evidence" title={`${party.name} relationship evidence`} /><Button type="button" size="sm" variant="ghost" onClick={() => void inspect(record)}>History</Button></div></TableCell>
          </TableRow>
        })}</TableBody>
      </Table></div>
    </Card>

    <Alert><Network /><AlertTitle>Incomplete Public Network</AlertTitle><AlertDescription>{network?.warnings.join(" ") || "No persisted business-network coverage is available for this company."}</AlertDescription></Alert>

    <Dialog open={Boolean(selected)} onOpenChange={(open) => { if (!open) setSelected(null) }}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader><DialogTitle>{selectedParty ? `${selectedParty.name} Relationship History` : "Relationship History"}</DialogTitle><DialogDescription>Observations are append-only. Later corrections or expiry dates do not erase earlier source evidence.</DialogDescription></DialogHeader>
        {selected ? <div className="space-y-4">
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded-md border p-3"><span className="text-xs text-muted-foreground">Type</span><strong className="mt-1 block text-sm">{typeLabels[selected.edge.relationshipType]}</strong></div>
            <div className="rounded-md border p-3"><span className="text-xs text-muted-foreground">Confidence</span><strong className="mt-1 block text-sm">{confidenceLabels[selected.observation.confidence]}</strong></div>
            <div className="rounded-md border p-3"><span className="text-xs text-muted-foreground">Current Exposure</span><strong className="mt-1 block text-sm">{exposure(selected)}</strong></div>
          </div>
          {historyLoading ? <p className="text-sm text-muted-foreground">Loading point-in-time history…</p> : null}
          {historyError ? <Alert variant="destructive"><AlertTitle>History Unavailable</AlertTitle><AlertDescription>{historyError}</AlertDescription></Alert> : null}
          {history ? <div className="max-h-72 overflow-auto rounded-lg border"><Table>
            <TableHeader><TableRow><TableHead>Known At</TableHead><TableHead>Confidence</TableHead><TableHead>Exposure</TableHead><TableHead>Kind</TableHead><TableHead>Source</TableHead></TableRow></TableHeader>
            <TableBody>{history.observations.map((observation) => <TableRow key={observation.observationId}>
              <TableCell className="font-mono text-[10px]">{new Date(observation.knownAt).toLocaleString()}</TableCell>
              <TableCell>{confidenceLabels[observation.confidence]}</TableCell>
              <TableCell>{observation.exposureValue === null ? "—" : `${observation.exposureValue} ${observation.exposureUnit}`}</TableCell>
              <TableCell>{observation.observationKind.replace("_", " ")}</TableCell>
              <TableCell><SourceEvidenceDialog evidence={history.evidence[observation.observationId] || []} label="Source" /></TableCell>
            </TableRow>)}</TableBody>
          </Table></div> : null}
          {selectedParty?.company?.primaryTicker ? <Button asChild variant="outline"><a href={labHref("intelligence", selectedParty.company.primaryTicker)}>Open Connected Company<ExternalLink /></a></Button> : <p className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">This counterparty remains unresolved. GBB preserves the disclosed name instead of guessing a public-company mapping.</p>}
        </div> : null}
      </DialogContent>
    </Dialog>
  </div>
}
