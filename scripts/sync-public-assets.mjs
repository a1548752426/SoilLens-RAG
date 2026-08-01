import fs from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const copies = [
  ["web/index.html", "public/demo.html"],
  ["web/app.js", "public/assets/app.js"],
  ["web/styles.css", "public/assets/styles.css"],
  ["web/vendor/echarts.min.js", "public/assets/vendor/echarts.min.js"],
  ["web/vendor/ECHARTS-LICENSE.txt", "public/assets/vendor/ECHARTS-LICENSE.txt"],
  ["demo_data/Sample_demo.xlsx", "public/Sample_demo.xlsx"],
];

for (const [source, destination] of copies) {
  const sourcePath = path.join(root, source);
  const destinationPath = path.join(root, destination);
  await fs.mkdir(path.dirname(destinationPath), { recursive: true });
  await fs.copyFile(sourcePath, destinationPath);
}

console.log(`Synced ${copies.length} public demo assets.`);
