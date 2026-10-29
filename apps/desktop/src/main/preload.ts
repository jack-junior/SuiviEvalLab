// Pont minimal et typé entre l'interface et le processus principal.

import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("sme", {
  call: (method: string, params?: Record<string, unknown>) => ipcRenderer.invoke("engine:call", method, params ?? {}),
  info: () => ipcRenderer.invoke("app:info"),
  onEvent: (listener: (event: { method: string; params: unknown }) => void) => {
    const handler = (_e: unknown, event: { method: string; params: unknown }) => listener(event);
    ipcRenderer.on("engine:event", handler);
    return () => ipcRenderer.removeListener("engine:event", handler);
  },
});
