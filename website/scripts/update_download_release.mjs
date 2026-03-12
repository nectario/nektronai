#!/usr/bin/env node

import { createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const siteDir = path.resolve(scriptDir, "..");
const manifestPath = path.join(siteDir, "assets", "downloads", "releases.json");
const downloadsDir = path.join(siteDir, "assets", "downloads");

const sourcePattern = /^grownet-source-(\d{4})-(\d{2})-(\d{2})-([a-f0-9]+)\.zip$/i;

function usage() {
  console.log(`Usage:
  node scripts/update_download_release.mjs source [--file <zip>] [--make-primary]
  node scripts/update_download_release.mjs lab --file <artifact> --version <version> [options]
  node scripts/update_download_release.mjs lab --clear

Source defaults:
  - scans assets/downloads for the newest grownet-source-YYYY-MM-DD-COMMIT.zip
  - updates releases.grownetSourceSnapshot in assets/downloads/releases.json

Lab options:
  --file <path>             Artifact file to publish
  --version <value>         Version string shown on the card
  --published <value>       Published label, e.g. "March 12, 2026"
  --label <value>           Button label (default: "Download installer")
  --title <value>           Card title override
  --summary <value>         Card summary override
  --eyebrow <value>         Card eyebrow override
  --href <value>            Public href override instead of deriving from --file
  --file-size <value>       File size label override
  --sha256 <value>          SHA-256 label override
  --make-primary            Point the hero CTA at this release
  --clear                   Reset the Lab App entry to "coming soon"

Notes:
  - If --file points outside the website folder, the script copies it into assets/downloads first.
`);
}

function parseArgs(argv) {
  const [command, ...rest] = argv;
  const options = {};

  for (let i = 0; i < rest.length; i += 1) {
    const token = rest[i];

    if (!token.startsWith("--")) {
      throw new Error(`Unexpected argument: ${token}`);
    }

    const key = token.slice(2);
    if (key === "make-primary" || key === "clear" || key === "help") {
      options[key] = true;
      continue;
    }

    const value = rest[i + 1];
    if (value == null || value.startsWith("--")) {
      throw new Error(`Missing value for --${key}`);
    }

    options[key] = value;
    i += 1;
  }

  return { command, options };
}

async function readManifest() {
  return JSON.parse(await fs.readFile(manifestPath, "utf8"));
}

async function writeManifest(manifest) {
  await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
}

async function pathExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

function toSiteRelative(assetPath) {
  const relativePath = path.relative(siteDir, assetPath);
  return relativePath.split(path.sep).join("/");
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatHumanDate(date) {
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  }).format(date);
}

async function sha256ForFile(filePath) {
  const buffer = await fs.readFile(filePath);
  return createHash("sha256").update(buffer).digest("hex").toUpperCase();
}

async function resolveAssetFile(inputPath) {
  const absolutePath = path.isAbsolute(inputPath)
    ? inputPath
    : path.resolve(process.cwd(), inputPath);

  if (!(await pathExists(absolutePath))) {
    throw new Error(`Artifact file not found: ${inputPath}`);
  }

  return absolutePath;
}

async function stageArtifactIfNeeded(filePath) {
  const relativeToSite = path.relative(siteDir, filePath);
  const isInsideSite = relativeToSite && !relativeToSite.startsWith("..") && !path.isAbsolute(relativeToSite);

  if (isInsideSite) {
    return filePath;
  }

  const stagedPath = path.join(downloadsDir, path.basename(filePath));
  await fs.copyFile(filePath, stagedPath);
  return stagedPath;
}

async function findLatestSourceZip() {
  const entries = await fs.readdir(downloadsDir, { withFileTypes: true });
  const candidates = entries
    .filter((entry) => entry.isFile() && sourcePattern.test(entry.name))
    .map((entry) => entry.name)
    .sort()
    .reverse();

  if (candidates.length === 0) {
    throw new Error(`No source snapshots matching ${sourcePattern} found in ${downloadsDir}`);
  }

  return path.join(downloadsDir, candidates[0]);
}

async function updateSourceRelease(options) {
  const resolvedSourceFile = options.file
    ? await resolveAssetFile(options.file)
    : await findLatestSourceZip();
  const sourceFile = await stageArtifactIfNeeded(resolvedSourceFile);

  const fileName = path.basename(sourceFile);
  const match = fileName.match(sourcePattern);
  if (!match) {
    throw new Error(`Source snapshot file name must match grownet-source-YYYY-MM-DD-COMMIT.zip: ${fileName}`);
  }

  const [, year, month, day, commit] = match;
  const publishedDate = new Date(`${year}-${month}-${day}T00:00:00Z`);
  const stats = await fs.stat(sourceFile);

  const manifest = await readManifest();
  manifest.releases.grownetSourceSnapshot = {
    ...manifest.releases.grownetSourceSnapshot,
    version: `${year}.${month}.${day} / ${commit}`,
    published: formatHumanDate(publishedDate),
    fileSize: formatBytes(stats.size),
    sha256: await sha256ForFile(sourceFile),
    downloadLabel: "Download ZIP",
    downloadHref: toSiteRelative(sourceFile),
    download: true,
  };

  if (options["make-primary"]) {
    manifest.hero.primaryReleaseId = "grownetSourceSnapshot";
    manifest.hero.primaryButtonLabel = "Download latest GrowNet source";
  }

  await writeManifest(manifest);
  console.log(`Updated grownetSourceSnapshot -> ${toSiteRelative(sourceFile)}`);
}

async function updateLabRelease(options) {
  const manifest = await readManifest();

  if (options.clear) {
    manifest.releases.grownetLabApp = {
      ...manifest.releases.grownetLabApp,
      version: "Pending first public build",
      published: "Builder-managed release line",
      fileSize: "TBD",
      sha256: "Will be added with the first installer build",
      downloadLabel: "Installer coming soon",
      downloadHref: "",
      download: false,
    };

    if (options["make-primary"]) {
      manifest.hero.primaryReleaseId = "grownetLabApp";
      manifest.hero.primaryButtonLabel = "Download GrowNet Lab App";
    }

    await writeManifest(manifest);
    console.log("Cleared grownetLabApp release entry.");
    return;
  }

  if (!options.file && !options.href) {
    throw new Error("Lab release update requires --file or --href");
  }
  if (!options.version) {
    throw new Error("Lab release update requires --version");
  }

  let assetPath = null;
  if (options.file) {
    assetPath = await stageArtifactIfNeeded(await resolveAssetFile(options.file));
  }

  const stats = assetPath ? await fs.stat(assetPath) : null;
  const published = options.published ?? formatHumanDate(new Date());

  manifest.releases.grownetLabApp = {
    ...manifest.releases.grownetLabApp,
    ...(options.eyebrow ? { eyebrow: options.eyebrow } : {}),
    ...(options.title ? { title: options.title } : {}),
    ...(options.summary ? { summary: options.summary } : {}),
    version: options.version,
    published,
    fileSize: options["file-size"] ?? (stats ? formatBytes(stats.size) : manifest.releases.grownetLabApp.fileSize),
    sha256: options.sha256 ?? (assetPath ? await sha256ForFile(assetPath) : manifest.releases.grownetLabApp.sha256),
    downloadLabel: options.label ?? "Download installer",
    downloadHref: options.href ?? (assetPath ? toSiteRelative(assetPath) : ""),
    download: true,
  };

  if (options["make-primary"]) {
    manifest.hero.primaryReleaseId = "grownetLabApp";
    manifest.hero.primaryButtonLabel = options.label ?? "Download GrowNet Lab App";
  }

  await writeManifest(manifest);
  console.log(`Updated grownetLabApp -> ${manifest.releases.grownetLabApp.downloadHref}`);
}

async function main() {
  const { command, options } = parseArgs(process.argv.slice(2));

  if (!command || command === "--help" || command === "-h" || command === "help" || options.help) {
    usage();
    return;
  }

  if (command === "source") {
    await updateSourceRelease(options);
    return;
  }

  if (command === "lab") {
    await updateLabRelease(options);
    return;
  }

  throw new Error(`Unknown command: ${command}`);
}

main().catch((error) => {
  console.error(error.message);
  usage();
  process.exitCode = 1;
});
