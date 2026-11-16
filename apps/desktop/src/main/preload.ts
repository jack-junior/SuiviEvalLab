// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

// Minimal, typed bridge between the interface and the main process.

import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("sme", {
  call: (method: string, params?: Record<string, unknown>) => ipcRenderer.invoke("engine:call", method, params ?? {}),
  info: () => ipcRenderer.invoke("app:info"),
  pick: (kind: string, defaultName?: string) => ipcRenderer.invoke("dialog:pick", kind, defaultName),
  recents: () => ipcRenderer.invoke("project:recents"),
  recentToken: (file: string) => ipcRenderer.invoke("project:recent-token", file),
  forget: (file: string) => ipcRenderer.invoke("project:forget", file),
  reveal: (file: string) => ipcRenderer.invoke("project:reveal", file),
  saveSummary: (file: string, summary: Record<string, number>) => ipcRenderer.invoke("project:summary", file, summary),
  openFile: (token: string) => ipcRenderer.invoke("file:reveal", token),
  portfolio: () => ipcRenderer.invoke("portfolio:dashboard"),
  portfolioExport: (kind: string, token: string, lang: string) =>
    ipcRenderer.invoke("portfolio:export", kind, token, lang),
  archive: (file: string, archived: boolean) => ipcRenderer.invoke("project:archive", file, archived),
  duplicate: (file: string, token: string, name: string) => ipcRenderer.invoke("project:duplicate", file, token, name),
  workspaceAgenda: (range: { start: string; end: string; lang: string }) =>
    ipcRenderer.invoke("workspace:agenda", range),
  updates: {
    get: () => ipcRenderer.invoke("updates:get"),
    check: () => ipcRenderer.invoke("updates:check"),
    setAuto: (auto: boolean) => ipcRenderer.invoke("updates:set-auto", auto),
    install: () => ipcRenderer.invoke("updates:install"),
    openNotes: (url: string) => ipcRenderer.invoke("app:open-notes", url),
    onState: (listener: (state: unknown) => void) => {
      const handler = (_e: unknown, state: unknown) => listener(state);
      ipcRenderer.on("updates:state", handler);
      return () => ipcRenderer.removeListener("updates:state", handler);
    },
  },
  onEvent: (listener: (event: { method: string; params: unknown }) => void) => {
    const handler = (_e: unknown, event: { method: string; params: unknown }) => listener(event);
    ipcRenderer.on("engine:event", handler);
    return () => ipcRenderer.removeListener("engine:event", handler);
  },
});
