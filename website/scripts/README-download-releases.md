# Download Release Updates

This guide is for updating the two managed download links on the NektronAI website:

- `GrowNet Lab App`
- `GrowNet source snapshot`

Do not edit `downloads.html` directly just to change download URLs or version text. The page is driven by the manifest at:

- `website/assets/downloads/releases.json`

The page reads that manifest through:

- `website/assets/site.js`

## Source Snapshot

The source snapshot release should use this filename pattern:

- `grownet-source-YYYY-MM-DD-COMMIT.zip`

Recommended release flow:

- keep the zip outside the website repo
- upload it to the `nektron.ai` downloads channel
- then update the manifest from the local file without copying it into git

Then run:

```bash
cd C:\Development\Projects\NektronAI\website
npm run update:downloads:source -- --file "C:\path\to\grownet-source-YYYY-MM-DD-COMMIT.zip" --external
```

That command will:

- update `releases.grownetSourceSnapshot`
- compute and write:
  - `downloadHref`
  - `version`
  - `published`
  - `fileSize`
  - `sha256`

If you prefer the older repo-staged workflow, you can still place the zip in `website/assets/downloads/` and run `npm run update:downloads:source` with no extra flags.

## Lab App

To publish a new GrowNet Lab App artifact, run:

```bash
cd C:\Development\Projects\NektronAI\website
npm run update:downloads:lab -- --file "C:\path\to\GrowNetLab.msi" --version "1.0.0" --published "March 12, 2026" --label "Download MSI" --external --make-primary
```

That command will update `releases.grownetLabApp` and keep the hero CTA pointed at the Lab App.

With `--external`, the script computes metadata from the local file but leaves the binary outside the website repo. This is the preferred workflow for release artifacts.

The script updates:

- `downloadHref`
- `version`
- `published`
- `fileSize`
- `sha256`
- `downloadLabel`

## Unpublish Lab App

If the Lab App should temporarily return to a not-yet-published state:

```bash
cd C:\Development\Projects\NektronAI\website
npm run update:downloads:lab -- --clear --make-primary
```

## Hero Button

The hero button is controlled by:

- `hero.primaryReleaseId`

inside:

- `website/assets/downloads/releases.json`

Current intended behavior:

- hero points to `grownetLabApp`
- source snapshot remains the second card

## Important Notes

- Keep using the manifest and updater script instead of editing the rendered download card text by hand.
- Release binaries should live on the website download host, not in git.
- `scripts/deploy.sh` excludes managed MSI/EXE/ZIP artifacts so normal website deploys do not delete bucket-hosted releases.
- After updating either release, verify `website/assets/downloads/releases.json`.
- Then deploy the website normally.
