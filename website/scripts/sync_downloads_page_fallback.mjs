#!/usr/bin/env node

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const siteDir = path.resolve(scriptDir, "..");
const manifestPath = path.join(siteDir, "assets", "downloads", "releases.json");
const downloadsPagePath = path.join(siteDir, "downloads.html");

function escapeForRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function escapeHtmlText(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeHtmlAttribute(value) {
  return escapeHtmlText(value).replace(/"/g, "&quot;");
}

function replaceFirstOrThrow(content, pattern, replacementFactory, description) {
  let didReplace = false;
  const updatedContent = content.replace(pattern, (...matches) => {
    didReplace = true;
    return replacementFactory(...matches);
  });

  if (!didReplace) {
    throw new Error(`Could not update downloads.html fallback for ${description}`);
  }

  return updatedContent;
}

function updateTagAttribute(content, dataAttributeMarker, attributeName, nextValue, description) {
  const pattern = new RegExp(
    `(<[^>]*${escapeForRegExp(dataAttributeMarker)}[^>]*?\\s${escapeForRegExp(attributeName)}=")([^"]*)(")`,
    "m",
  );

  return replaceFirstOrThrow(
    content,
    pattern,
    (fullMatch, prefix, previousValue, suffix) => `${prefix}${escapeHtmlAttribute(nextValue)}${suffix}`,
    description,
  );
}

function updateElementText(content, dataAttributeMarker, nextText, description) {
  const pattern = new RegExp(
    `(<[^>]*${escapeForRegExp(dataAttributeMarker)}[^>]*>)([\\s\\S]*?)(</[^>]+>)`,
    "m",
  );

  return replaceFirstOrThrow(
    content,
    pattern,
    (fullMatch, prefix, previousValue, suffix) => `${prefix}${escapeHtmlText(nextText)}${suffix}`,
    description,
  );
}

function updateScopedElementText(content, releaseId, dataAttributeValue, nextText, description) {
  const articlePattern = new RegExp(
    `(<article[^>]*data-download-release="${escapeForRegExp(releaseId)}"[^>]*>[\\s\\S]*?</article>)`,
    "m",
  );

  return replaceFirstOrThrow(
    content,
    articlePattern,
    (articleMatch) =>
      updateElementText(
        articleMatch,
        `data-download-field="${dataAttributeValue}"`,
        nextText,
        `${description} (${releaseId})`,
      ),
    `${description} article (${releaseId})`,
  );
}

function updateScopedLink(content, releaseId, nextHref, nextLabel) {
  const articlePattern = new RegExp(
    `(<article[^>]*data-download-release="${escapeForRegExp(releaseId)}"[^>]*>[\\s\\S]*?</article>)`,
    "m",
  );

  return replaceFirstOrThrow(
    content,
    articlePattern,
    (articleMatch) => {
      let updatedArticle = updateTagAttribute(
        articleMatch,
        "data-download-link",
        "href",
        nextHref,
        `download href (${releaseId})`,
      );
      updatedArticle = updateElementText(
        updatedArticle,
        "data-download-label",
        nextLabel,
        `download label (${releaseId})`,
      );
      return updatedArticle;
    },
    `download card (${releaseId})`,
  );
}

export async function syncDownloadsPageFallback(manifestObject) {
  const heroRelease = manifestObject.releases[manifestObject.hero.primaryReleaseId];
  if (!heroRelease) {
    throw new Error(`Hero primary release is missing: ${manifestObject.hero.primaryReleaseId}`);
  }

  let htmlText = await fs.readFile(downloadsPagePath, "utf8");

  htmlText = updateTagAttribute(
    htmlText,
    "data-download-hero-link",
    "href",
    heroRelease.downloadHref ?? "",
    "hero href",
  );
  htmlText = updateElementText(
    htmlText,
    "data-download-hero-label",
    manifestObject.hero.primaryButtonLabel ?? heroRelease.downloadLabel ?? "Download",
    "hero label",
  );
  htmlText = updateElementText(
    htmlText,
    "data-download-hero-primary-version",
    heroRelease.version ?? "",
    "hero primary version",
  );
  htmlText = updateElementText(
    htmlText,
    "data-download-hero-artifacts",
    manifestObject.hero.artifacts ?? "",
    "hero artifacts",
  );

  for (const [releaseId, releaseEntry] of Object.entries(manifestObject.releases)) {
    htmlText = updateScopedElementText(htmlText, releaseId, "eyebrow", releaseEntry.eyebrow ?? "", "eyebrow");
    htmlText = updateScopedElementText(htmlText, releaseId, "title", releaseEntry.title ?? "", "title");
    htmlText = updateScopedElementText(htmlText, releaseId, "summary", releaseEntry.summary ?? "", "summary");
    htmlText = updateScopedElementText(htmlText, releaseId, "version", releaseEntry.version ?? "", "version");
    htmlText = updateScopedElementText(htmlText, releaseId, "published", releaseEntry.published ?? "", "published");
    htmlText = updateScopedElementText(htmlText, releaseId, "fileSize", releaseEntry.fileSize ?? "", "file size");
    htmlText = updateScopedElementText(htmlText, releaseId, "sha256", releaseEntry.sha256 ?? "", "sha256");
    htmlText = updateScopedLink(
      htmlText,
      releaseId,
      releaseEntry.downloadHref ?? "",
      releaseEntry.downloadLabel ?? "Download",
    );
  }

  await fs.writeFile(downloadsPagePath, htmlText, "utf8");
}

async function main() {
  const manifestObject = JSON.parse(await fs.readFile(manifestPath, "utf8"));
  await syncDownloadsPageFallback(manifestObject);
  console.log("Synced downloads.html fallback from assets/downloads/releases.json");
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
