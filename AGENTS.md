# AGENTS.md

Guidance for coding agents and contributors working in this repository.

## Repository layout

- `watchface/`: Android resource-only Watch Face Format project.
- `debloat/`: reversible ADB package-management scripts.
- `.github/workflows/ci.yml`: public CI checks.

## General rules

- Keep changes scoped and preserve user-authored design decisions.
- Do not commit `local.properties`, build output, raw screenshots (the normalized
  `preview.png` asset is intentional), APK/AAB files, keystores, signing
  properties, credentials, or private device addresses.
- Never place release signing secrets in Gradle files. Use the ignored
  `watchface/keystore.properties` file described by its `.example` template.
- Run the relevant checks before reporting completion.
- Keep documentation and commands usable from the directory that contains the
  corresponding README.

## Watch face

- Maintain Watch Face Format **v1** compatibility unless explicitly requested.
- The app identity is `id.mustofa.wf.black`; retain it unless requested.
- Preserve the “Khawlah Zahra Fasihah” dedication unless requested.
- Do not add weather, third-party providers, or complication slots without an
  explicit request.
- Preserve the pure-black background and system-controlled notification dot.
- Moon and date-rule bitmaps belong in `res/drawable-nodpi`; WFF `PartImage`
  does not render VectorDrawables on the tested runtime.
- Keep the moon `Condition` before `AnalogClock` so hands render above it.
- Regenerate moon assets after changing their geometry or colors:

  ```bash
  cd watchface
  python3 tools/make-moon-icons.py
  ```

- `preview.png` is an on-device screenshot. Replace it using:

  ```bash
  ./tools/make-preview.sh path/to/clean-screenshot.png
  ```

- Validate and build:

  ```bash
  cd watchface
  ./tools/validate.sh
  ./gradlew :face:assembleDebug :face:assembleRelease
  ```

## Debloat scripts

- Every action in `debloat/apply.sh` must remain reversible in
  `debloat/rollback.sh`.
- Keep package lists synchronized between both scripts and the README.
- Retain the device preflight, warning, confirmation prompt, and `--dry-run`
  behavior in `apply.sh`.
- Clearly document changes affecting accessibility, emergency alerts, input,
  payments, connectivity, or app installation.
- Syntax-check scripts after edits:

  ```bash
  bash -n debloat/apply.sh debloat/rollback.sh
  ```

## Public release checks

Before publishing, verify that `git status --ignored` shows local SDK files and
build output as ignored, search tracked text for private paths or addresses,
and confirm that no APK or signing material is tracked.
