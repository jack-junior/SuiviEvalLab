# 0003. Windows only for version 1

- Status: accepted
- Date: 2026-10-29

## Context
Most target users work on Windows laptops. Embedding R on macOS requires relocation work, code signing and notarisation with a paid Apple account.

## Decision
Version 1 targets Windows 10 and 11 (x64) only. The architecture stays portable so macOS can be added later. The installer is unsigned during development; signing is added before the public beta.

## Consequences
No Apple cost or macOS risk now. Testers see a SmartScreen warning until the installer is signed.
