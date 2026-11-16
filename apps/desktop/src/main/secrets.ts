// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Tokens and passwords of the servers a project connects to (Kobo, ODK Central,
// DHIS2). They are encrypted with the key store of the operating system (DPAPI on
// Windows) and kept in the user's folder, never in the project file and never
// sent back to the interface. The engine receives one for the call that needs it.

import { app, safeStorage } from "electron";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const file = () => path.join(app.getPath("userData"), "secrets.json");

function readAll(): Record<string, string> {
  try {
    return JSON.parse(readFileSync(file(), "utf-8")) as Record<string, string>;
  } catch {
    return {};
  }
}

export function setSecret(id: string, secret: string): void {
  const all = readAll();
  if (!secret) delete all[id];
  else if (safeStorage.isEncryptionAvailable()) all[id] = `enc:${safeStorage.encryptString(secret).toString("base64")}`;
  // Without a key store (some Linux sessions), the secret is only obscured: said in the guide.
  else all[id] = `b64:${Buffer.from(secret, "utf-8").toString("base64")}`;
  writeFileSync(file(), JSON.stringify(all), { encoding: "utf-8", mode: 0o600 });
}

export function getSecret(id: string): string | undefined {
  const value = readAll()[id];
  if (!value) return undefined;
  try {
    if (value.startsWith("enc:")) return safeStorage.decryptString(Buffer.from(value.slice(4), "base64"));
    if (value.startsWith("b64:")) return Buffer.from(value.slice(4), "base64").toString("utf-8");
  } catch {
    return undefined;
  }
  return undefined;
}

export const hasSecret = (id: string) => !!readAll()[id];
