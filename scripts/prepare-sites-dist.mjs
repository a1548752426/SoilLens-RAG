import { copyFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const projectRoot = process.cwd();
const distDir = path.join(projectRoot, "dist");
const serverDir = path.join(distDir, "server");
const hostingDir = path.join(distDir, ".openai");

await mkdir(serverDir, { recursive: true });
await mkdir(hostingDir, { recursive: true });

// Sites loads the production module from this stable path. Vinext's Pages
// Router build names the equivalent generated module entry.js.
await writeFile(
  path.join(serverDir, "index.js"),
  'export * from "./entry.js";\n',
  "utf8",
);

await copyFile(
  path.join(projectRoot, ".openai", "hosting.json"),
  path.join(hostingDir, "hosting.json"),
);

console.log("Prepared Sites deployment entrypoint and metadata.");
