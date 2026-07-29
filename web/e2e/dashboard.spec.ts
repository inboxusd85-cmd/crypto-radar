import { expect, test } from "@playwright/test"

const primaryRoutes = ["/", "/signals", "/reviews", "/events", "/health", "/github"]

test("production-like server exposes health and preserves the static asset namespace @desktop", async ({ request }) => {
  const health = await request.get("/api/v1/health")
  expect(health.ok()).toBe(true)
  expect((await health.json()).status).toBe("ok")

  const missingAsset = await request.get("/assets/not-a-dashboard-route.js")
  expect(missingAsset.status()).toBe(404)
})

test("desktop primary routes expose the active navigation item @desktop", async ({ page }) => {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  page.on("pageerror", error => pageErrors.push(error.message))
  page.on("console", message => {
    if (message.type() === "error") consoleErrors.push(message.text())
  })

  for (const route of primaryRoutes) {
    await page.goto(route, { waitUntil: "commit" })
    expect(page.viewportSize()).toEqual({ width: 1280, height: 720 })
    await expect(page.locator(".room-content")).toBeAttached()
    await expect(page.locator(".room-nav")).toBeVisible()
    await expect(page.locator(".room-mobile")).toBeHidden()
    await expect(page.getByRole("navigation", { name: "Основная навигация" }).locator('a[aria-current="page"]')).toHaveAttribute("href", route)
    await expect(page.locator('a[href^="/assets/"]')).toHaveCount(0)
  }

  expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
  expect(consoleErrors, `console errors: ${consoleErrors.join(" | ")}`).toEqual([])
})

test("desktop GitHub Watch exposes enabled baseline and observed events @desktop", async ({ page }) => {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  const failedResponses: string[] = []
  page.on("pageerror", error => pageErrors.push(error.message))
  page.on("console", message => {
    if (message.type() === "error") consoleErrors.push(message.text())
  })
  page.on("response", response => {
    const request = response.request()
    if (["xhr", "fetch"].includes(request.resourceType()) && response.status() >= 400) {
      failedResponses.push(`${response.status()} ${request.method()} ${response.url()}`)
    }
  })

  await page.goto("/github", { waitUntil: "commit" })
  await expect(page.locator(".room-content")).toBeAttached()
  await expect(page.getByText("GitHub Watch").first()).toBeVisible()
  await expect(page.getByText("enabled", { exact: true })).toBeVisible()
  const banner = page.locator(".github-banner p")
  await expect(banner).toContainText(/\d+ repositories · \d+ observed events/)
  await expect(page.getByRole("button", { name: "Check now" })).toBeVisible()
  const renderedEvents = await page.locator(".github-event").count()
  const bannerText = await banner.textContent()
  const reportedEvents = Number(bannerText?.match(/· (\d+) observed events/)?.[1])
  expect(reportedEvents).toBeGreaterThanOrEqual(renderedEvents)
  if (reportedEvents > 0) {
    await expect(banner).toContainText("latest")
    await expect(page.locator(".github-event").first()).toBeVisible()
    await expect(page.locator(".github-event time").first()).toBeVisible()
  } else {
    await expect(page.getByText("GitHub events not collected.")).toBeVisible()
  }

  expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
  expect(consoleErrors, `console errors: ${consoleErrors.join(" | ")}`).toEqual([])
  expect(failedResponses, `failed API responses: ${failedResponses.join(" | ")}`).toEqual([])
})

test("desktop Validation exposes the isolated archive gate @desktop", async ({ page }) => {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  page.on("pageerror", error => pageErrors.push(error.message))
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()) })
  await page.goto("/reviews", { waitUntil: "commit" })
  const heading = page.getByRole("heading", { name: "Archive validation" })
  await expect(heading).toBeVisible({ timeout: 30_000 })
  const panel = heading.locator("../..")
  await expect(panel).toContainText("isolated candles · read-only")
  await expect(panel).toContainText(/train (ready|blocked)/)
  await expect(panel).toContainText(/test (ready|blocked)/)
  await expect(panel).toContainText("Promotion")
  await expect(page.locator(".live-chip")).toContainText("execution disabled · review enabled")
  expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
  expect(consoleErrors, `console errors: ${consoleErrors.join(" | ")}`).toEqual([])
})

test("mobile menu exposes every primary route @mobile", async ({ page }) => {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  page.on("pageerror", error => pageErrors.push(error.message))
  page.on("console", message => {
    if (message.type() === "error") consoleErrors.push(message.text())
  })

  await page.goto("/events", { waitUntil: "commit" })
  expect(page.viewportSize()).toEqual({ width: 390, height: 844 })
  await expect(page.locator(".room-mobile")).toBeVisible()
  await expect(page.locator(".room-nav")).toBeHidden()
  await expect(page.locator(".room-mobile")).toBeAttached()
  await expect(page.getByRole("button", { name: "Меню" })).toBeVisible()
  await page.getByRole("button", { name: "Меню" }).click()
  const nav = page.getByRole("navigation", { name: "Мобильная навигация" })
  for (const label of ["Обзор", "Сигналы", "Validation", "Журнал", "Система", "GitHub Watch"]) {
    await expect(nav).toContainText(label)
  }

  expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
  expect(consoleErrors, `console errors: ${consoleErrors.join(" | ")}`).toEqual([])
})

test("mobile GitHub Watch remains read-only with enabled baseline @mobile", async ({ page }) => {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  page.on("pageerror", error => pageErrors.push(error.message))
  page.on("console", message => {
    if (message.type() === "error") consoleErrors.push(message.text())
  })

  await page.goto("/github", { waitUntil: "commit" })
  expect(page.viewportSize()).toEqual({ width: 390, height: 844 })
  await expect(page.locator(".room-mobile")).toBeVisible()
  await expect(page.locator(".room-nav")).toBeHidden()
  await expect(page.locator(".live-chip")).toContainText("execution disabled · review enabled")
  await expect(page.getByText("enabled", { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Check now" })).toBeVisible()
  const banner = page.locator(".github-banner p")
  await expect(banner).toContainText(/\d+ repositories · \d+ observed events/)
  const renderedEvents = await page.locator(".github-event").count()
  const bannerText = await banner.textContent()
  const reportedEvents = Number(bannerText?.match(/· (\d+) observed events/)?.[1])
  expect(reportedEvents).toBeGreaterThanOrEqual(renderedEvents)
  if (reportedEvents > 0) {
    await expect(banner).toContainText("latest")
    await expect(page.locator(".github-event").first()).toBeVisible()
    await expect(page.locator(".github-event time").first()).toBeVisible()
  } else {
    await expect(page.getByText("GitHub events not collected.")).toBeVisible()
  }

  expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
  expect(consoleErrors, `console errors: ${consoleErrors.join(" | ")}`).toEqual([])
})

test("desktop asset detail exposes the indicator snapshot status @desktop", async ({ page }) => {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  const failedResponses: string[] = []
  page.on("pageerror", error => pageErrors.push(error.message))
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()) })
  page.on("response", response => {
    const request = response.request()
    if (["xhr", "fetch"].includes(request.resourceType()) && response.status() >= 400) failedResponses.push(`${response.status()} ${request.method()} ${response.url()}`)
  })
  await page.goto("/asset/BTC", { waitUntil: "commit" })
  await expect(page.getByRole("heading", { name: "BTC" })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole("heading", { name: "Основные индикаторы" })).toBeVisible({ timeout: 30_000 })
  await expect(page.locator(".room-nav")).toBeVisible()
  await expect(page.locator(".live-chip")).toContainText("execution disabled · review enabled")
  const indicatorSnapshot = page.getByLabel("Последнее обновление индикаторов")
  await expect(indicatorSnapshot).toContainText("актуально", { timeout: 30_000 })
  await expect(indicatorSnapshot).toHaveText(/обновлено .+ · актуально · \d+(м|ч|д)/, { timeout: 30_000 })
  expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
  expect(consoleErrors, `console errors: ${consoleErrors.join(" | ")}`).toEqual([])
  expect(failedResponses, `failed API responses: ${failedResponses.join(" | ")}`).toEqual([])
})

test("mobile Validation keeps the archive gate readable without overflow @mobile", async ({ page }) => {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  page.on("pageerror", error => pageErrors.push(error.message))
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()) })
  await page.goto("/reviews", { waitUntil: "commit" })
  expect(page.viewportSize()).toEqual({ width: 390, height: 844 })
  const heading = page.getByRole("heading", { name: "Archive validation" })
  await expect(heading).toBeVisible({ timeout: 30_000 })
  await expect(page.locator(".room-mobile")).toBeVisible()
  await expect(page.locator(".room-nav")).toBeHidden()
  await expect(page.locator(".live-chip")).toContainText("execution disabled · review enabled")
  await expect(heading.locator("../..")).toContainText("Promotion")
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
  expect(consoleErrors, `console errors: ${consoleErrors.join(" | ")}`).toEqual([])
})

test("mobile asset detail remains read-only and loads its taxonomy @mobile", async ({ page }) => {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  const failedRequests: string[] = []
  const failedResponses: string[] = []
  page.on("pageerror", error => pageErrors.push(error.message))
  page.on("console", message => {
    if (message.type() === "error") consoleErrors.push(message.text())
  })
  page.on("requestfailed", request => failedRequests.push(`${request.method()} ${request.url()} — ${request.failure()?.errorText ?? "failed"}`))
  page.on("response", response => {
    const request = response.request()
    if (["xhr", "fetch"].includes(request.resourceType()) && response.status() >= 400) {
      failedResponses.push(`${response.status()} ${request.method()} ${response.url()}`)
    }
  })

  await page.goto("/asset/ETH", { waitUntil: "commit" })
  expect(page.viewportSize()).toEqual({ width: 390, height: 844 })
  await expect(page.getByRole("heading", { name: "ETH" })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole("heading", { name: "Основные индикаторы" })).toBeVisible({ timeout: 30_000 })
  await expect(page.locator(".room-mobile")).toBeVisible()
  await expect(page.locator(".room-nav")).toBeHidden()
  await expect(page.locator(".room-content")).toBeAttached()
  await expect(page.locator(".live-chip")).toContainText("execution disabled · review enabled")
  const indicatorSnapshot = page.getByLabel("Последнее обновление индикаторов")
  await expect(indicatorSnapshot).toContainText("актуально", { timeout: 30_000 })
  await expect(indicatorSnapshot).toHaveText(/обновлено .+ · актуально · \d+(м|ч|д)/, { timeout: 30_000 })

  expect(pageErrors, `page errors: ${pageErrors.join(" | ")}`).toEqual([])
  expect(consoleErrors, `console errors: ${consoleErrors.join(" | ")}`).toEqual([])
  expect(failedRequests, `failed requests: ${failedRequests.join(" | ")}`).toEqual([])
  expect(failedResponses, `failed API responses: ${failedResponses.join(" | ")}`).toEqual([])
})
