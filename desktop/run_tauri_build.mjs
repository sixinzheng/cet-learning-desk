import { spawn } from "node:child_process";
import { readdir, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const desktopRoot = fileURLToPath(new URL(".", import.meta.url));
const cliPath = path.join(desktopRoot, "node_modules", "@tauri-apps", "cli", "tauri.js");
const bundleDir = path.join(desktopRoot, "src-tauri", "target", "release", "bundle", "nsis");
const defaultKeyPath = process.env.LOCALAPPDATA
  ? path.join(process.env.LOCALAPPDATA, "CETLearningDesk", "signing", "tauri-updater.key")
  : "";
const privateKeyPath = process.env.TAURI_SIGNING_PRIVATE_KEY_PATH || defaultKeyPath;
const password = process.env.TAURI_SIGNING_PRIVATE_KEY_PASSWORD ?? "";

function runCli(args) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [cliPath, ...args], {
      cwd: desktopRoot,
      env: process.env,
      stdio: "inherit",
      shell: false,
    });
    child.once("error", reject);
    child.once("exit", (code, signal) => {
      if (signal) return reject(new Error(`Tauri CLI terminated by ${signal}`));
      if (code !== 0) return reject(new Error(`Tauri CLI exited with code ${code}`));
      resolve();
    });
  });
}

async function newestInstaller() {
  const names = (await readdir(bundleDir)).filter((name) => name.toLowerCase().endsWith("-setup.exe"));
  if (!names.length) throw new Error(`No NSIS installer found in ${bundleDir}`);
  const entries = await Promise.all(names.map(async (name) => {
    const fullPath = path.join(bundleDir, name);
    return {fullPath, mtimeMs: (await stat(fullPath)).mtimeMs};
  }));
  entries.sort((a, b) => b.mtimeMs - a.mtimeMs);
  return entries[0].fullPath;
}

if (!privateKeyPath) throw new Error("TAURI_SIGNING_PRIVATE_KEY_PATH is required.");

// The first updater key has an empty password. Build without integrated
// updater signing, then call the standalone signer with an explicit empty
// password argument so local and GitHub Actions builds remain non-interactive.
await runCli([
  "build",
  "--bundles", "nsis",
  "--config", JSON.stringify({bundle: {createUpdaterArtifacts: false}}),
]);

const installer = await newestInstaller();
await runCli([
  "signer", "sign",
  "--private-key-path", privateKeyPath,
  "--password", password,
  installer,
]);
console.log(`Signed updater artifact: ${installer}.sig`);
