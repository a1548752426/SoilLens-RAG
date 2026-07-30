import { copyFile, cp, mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";
import vinext from "vinext";

const projectRoot = process.cwd();
const distDir = path.join(projectRoot, "dist");
const serverDir = path.join(distDir, "server");
const bundledServerDir = path.join(distDir, ".sites-server");
const hostingDir = path.join(distDir, ".openai");
const pagesWorkerEntry = fileURLToPath(
  import.meta.resolve("vinext/server/pages-router-entry"),
);

await mkdir(serverDir, { recursive: true });
await mkdir(hostingDir, { recursive: true });

const bundleServerDependencies = {
  name: "soillens:bundle-sites-worker-dependencies",
  enforce: "post",
  configEnvironment(name, config) {
    if (name !== "ssr" || !Array.isArray(config.resolve?.external)) return;
    config.resolve.external = config.resolve.external.filter(
      (id) =>
        id !== "react" &&
        id !== "react-dom" &&
        id !== "react-dom/server" &&
        id !== "react-dom/server.edge" &&
        id !== "react/jsx-runtime",
    );
  },
};

// Sites runs a Worker-style fetch entrypoint and deploys only dist/. Build
// Vinext's Pages Router worker with all browser-framework dependencies bundled.
await build({
  configFile: false,
  root: projectRoot,
  publicDir: false,
  logLevel: "warn",
  plugins: [
    vinext({ disableAppRouter: true }),
    bundleServerDependencies,
  ],
  build: {
    ssr: pagesWorkerEntry,
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
