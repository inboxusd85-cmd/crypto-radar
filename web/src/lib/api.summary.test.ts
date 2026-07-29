import { describe, expect, it, vi } from "vitest"

import { getReviewSummary } from "./api"

describe("review summary API", () => {
  it("requests aggregate quality summary", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ reviewed_count: 0 }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await getReviewSummary()

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/reviews/summary", expect.any(Object))
  })
})
