import { useState } from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { createOptionDraft, FALLBACK_OPTION_TEMPLATES, replaceOptionTemplate } from "@/features/option-lab/option-presets"
import { PositionBuilder } from "@/features/option-lab/position-builder"
import type { OptionPositionCreate, OptionPositionTemplate } from "@/lib/types"

function Harness() {
  const [draft, setDraft] = useState<OptionPositionCreate>(() => createOptionDraft(FALLBACK_OPTION_TEMPLATES[0]))
  const selectTemplate = (template: OptionPositionTemplate) => setDraft((current) => replaceOptionTemplate(current, template))
  return <PositionBuilder draft={draft} templates={FALLBACK_OPTION_TEMPLATES} chain={null} chainLoading={false} chainError="" onChange={setDraft} onSelectTemplate={selectTemplate} onLoadChain={() => undefined} onSelectContract={() => undefined} />
}

describe("Option Lab position builder", () => {
  it("replaces the leg canvas when a different recipe is selected", async () => {
    const user = userEvent.setup()
    render(<Harness />)

    expect(screen.getByLabelText("Leg 1 strike")).toBeInTheDocument()
    expect(screen.queryByLabelText("Leg 2 strike")).not.toBeInTheDocument()
    await user.click(screen.getByRole("tab", { name: "Defined Risk" }))
    await user.click(screen.getByRole("button", { name: /Bull Call Spread/ }))
    expect(screen.getByLabelText("Leg 2 strike")).toBeInTheDocument()

    await user.click(screen.getByRole("tab", { name: "Income" }))
    await user.click(screen.getByRole("button", { name: /Covered Call/ }))
    expect(screen.queryByLabelText("Leg 2 strike")).not.toBeInTheDocument()
    expect(screen.getByLabelText("Covered shares")).toHaveValue(100)
  })
})
