const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("appInfo", {
  name: "投标"
});

contextBridge.exposeInMainWorld("backend", {
  ensure: (apiBase) => ipcRenderer.invoke("backend:ensure", apiBase),
  diagnose: (apiBase) => ipcRenderer.invoke("backend:diagnose", apiBase)
});
