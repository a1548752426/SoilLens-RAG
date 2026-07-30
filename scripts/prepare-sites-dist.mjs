import { copyFile, cp, mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { build } from "vite";

const projectRoot = process.cwd();
const distDir = path.join(projectRoot, "dist");
const serverDir = path.join(distDir, "server");
const bundledServerDir = path.join(distDir, ".sites-server");
const hostingDir = path.join(distDir, ".openai");

await mkdir(serverDir, { recursive: true });
await mkdir(hostingDir, { recursive: true });

// Sites deploys only dist/, so bundle Vinext's external React dependencies
// into the stable server/index.js entrypoint used by the production runtime.
await build({
  configFile: false,
  root: projectRoot,
  publicDir: false,
  logLevel: "warn",
  build: {
    ssr: path.join(serverDir, "entry.js"),
    outDir: bundledServerDir,
    emptyOutDir: true,
    minify: true,
    rolldownOptions: {
      external: (id) => id.startsWith("node:"),
      output: {
        entryFileNames: "index.js",
        chunkFileNames: "sites-assets/[name]-[hash].js",
      },
    },
  },
  ssr: {
    noExternal: true,
  },
});

await cp(bundledServerDir, serverDir, { recursive: true, force: true });
await rm(bundledServerDir, { recursive: true, force: true });
await writeFile(
  path.join(serverDir, "vinext-externals.json"),
  "[]\n",
  "utf8",
);

await copyFile(
  path.join(projectRoot, ".openai", "hosting.json"),
  path.join(hostingDir, "hosting.json"),
);

console.log("Prepared Sites deployment entrypoint and metadata.");
