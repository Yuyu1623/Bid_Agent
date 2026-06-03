const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("appInfo", {
  name: "Dowell投标"
});

contextBridge.exposeInMainWorld("backend", {
  ensure: (apiBase) => ipcRenderer.invoke("backend:ensure", apiBase)
});
