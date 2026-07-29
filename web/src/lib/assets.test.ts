import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

describe("production asset boundaries", () => {
  it("keeps dashboard entrypoints self-contained", () => {
    const files = ["index.html", "src/main.tsx", "src/App.tsx", "src/styles.css"]
    const source = files.map((file) => readFileSync(resolve(process.cwd(), file), "utf8")).join("\n")
    expect(source).not.toMatch(/@import\s+url\(/i)
    expect(source).not.toMatch(/url\(\s*https?:/i)
    expect(source).not.toMatch(/(?:src|href)=['\"]https?:/i)
  })
})
