import { describe, expect, it, vi } from "vitest"

import { getReviews, updateReview } from "./api"

describe("review API functions", () => {
  it("lists pending reviews", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ reviews: [], count: 0 }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await getReviews("pending")

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/reviews?status=pending&limit=100", expect.any(Object))
  })

  it("updates a review with analyst note", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ event_id: "event-1", status: "confirmed", note: "Проверено" }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await updateReview("event-1", "confirmed", "Проверено")

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/reviews/event-1", expect.objectContaining({
      method: "PUT",
      body: JSON.stringify({ status: "confirmed", note: "Проверено" }),
    }))
  })
})
