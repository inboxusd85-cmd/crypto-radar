import { existsSync, readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"

const files = ["dist/index.html"]
const assetsDir = "dist/assets"

if (!existsSync(files[0])) {
  console.error(`Missing ${files[0]}; run npm run build first`)
  process.exit(1)
}

if (!existsSync(assetsDir)) {
  console.error(`Missing ${assetsDir}; run npm run build first`)
  process.exit(1)
}

for (const name of readdirSync(assetsDir)) {
  if (name.endsWith(".css")) files.push(join(assetsDir, name))
}

if (files.length === 1) {
  console.error(`Missing CSS production asset in ${assetsDir}`)
  process.exit(1)
}

const externalResource = /https?:\/\//i
const hits = files.flatMap((file) => {
  const lines = readFileSync(file, "utf8").split(/\r?\n/)
  return lines.flatMap((line, index) => externalResource.test(line) ? [`${file}:${index + 1}:${line}`] : [])
})

if (hits.length) {
  console.error("External HTML/CSS production asset reference detected")
  console.error(hits.join("\n"))
  process.exit(1)
}

console.log(`Self-contained production assets verified: ${files.join(", ")}`)
