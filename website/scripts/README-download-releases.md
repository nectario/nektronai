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

Place the new zip in:

- `website/assets/downloads/`

Then run:

```bash
cd C:\Development\Projects\NektronAI\website
npm run update:downloads:source
```

That command will:

- find the newest matching source zip
- update `releases.grownetSourceSnapshot`
- compute and write:
  - `downloadHref`
  - `version`
  - `published`
  - `fileSize`
  - `sha256`

## Lab App

To publish a new GrowNet Lab App artifact, run:

```bash
cd C:\Development\Projects\NektronAI\website
node scripts/update_download_release.mjs lab --file "C:\path\to\GrowNetLabInstaller.exe" --version "1.0.0" --published "March 12, 2026" --label "Download installer" --make-primary
```

That command will update `releases.grownetLabApp` and keep the hero CTA pointed at the Lab App.

If `--file` points outside the website folder, the script copies the artifact into:

- `website/assets/downloads/`

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
node scripts/update_download_release.mjs lab --clear --make-primary
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
- After updating either release, verify `website/assets/downloads/releases.json`.
- Then deploy the website normally.
