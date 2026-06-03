const { app, BrowserWindow, ipcMain } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");
const fs = require("fs");

let backendProcess = null;
let backendPort = null;

function createWindow() {
  const win = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 960,
    minHeight: 680,
    title: "Dowell投标",
    backgroundColor: "#f6f7f9",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  win.loadFile(path.join(__dirname, "renderer.html"));
}

function parseBackendTarget(apiBase) {
  const url = new URL(apiBase || "http://127.0.0.1:8000");
  const port = Number(url.port || (url.protocol === "https:" ? 443 : 80));
  if (!Number.isInteger(port) || port <= 0 || port > 65535) {
    throw new Error(`后端端口无效：${url.port}`);
  }
  return {
    host: url.hostname || "127.0.0.1",
    port
  };
}

function findBackendDirectory() {
  const exeDir = path.dirname(app.getPath("exe"));
  const candidates = [
    path.resolve(__dirname, ".."),
    path.resolve(process.cwd(), ".."),
    path.resolve(exeDir, "..", ".."),
    path.join(process.resourcesPath || "", "backend")
  ];

  for (const candidate of candidates) {
    if (candidate && fs.existsSync(path.join(candidate, "bid_parser_api.py"))) {
      return candidate;
    }
  }

  throw new Error("找不到后端文件 bid_parser_api.py，请确认 exe 位于项目目录内，或将后端文件放入 resources/backend。");
}

function checkBackend(port) {
  return new Promise((resolve) => {
    const request = http.get(
      {
        host: "127.0.0.1",
        port,
        path: "/openapi.json",
        timeout: 1800
      },
      (response) => {
        response.resume();
        resolve(response.statusCode >= 200 && response.statusCode < 500);
      }
    );
    request.on("timeout", () => {
      request.destroy();
      resolve(false);
    });
    request.on("error", () => resolve(false));
  });
}

async function waitForBackend(port, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await checkBackend(port)) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 450));
  }
  return false;
}

function stopOwnedBackend() {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
  backendProcess = null;
  backendPort = null;
}

async function ensureBackend(apiBase) {
  const { port } = parseBackendTarget(apiBase);

  if (backendPort === port && (await checkBackend(port))) {
    return { port, status: "running" };
  }

  if (await checkBackend(port)) {
    stopOwnedBackend();
    backendPort = port;
    return { port, status: "external-running" };
  }

  if (backendPort !== port) {
    stopOwnedBackend();
  }

  const backendDir = findBackendDirectory();
  backendProcess = spawn(
    "python",
    ["-m", "uvicorn", "bid_parser_api:app", "--host", "127.0.0.1", "--port", String(port)],
    {
      cwd: backendDir,
      windowsHide: true,
      stdio: "ignore",
      detached: false
    }
  );
  backendPort = port;

  backendProcess.on("exit", () => {
    backendProcess = null;
    backendPort = null;
  });

  const ok = await waitForBackend(port);
  if (!ok) {
    stopOwnedBackend();
    throw new Error(`后端启动失败，请检查 Python 依赖和端口 ${port} 是否可用。`);
  }

  return { port, status: "started" };
}

ipcMain.handle("backend:ensure", async (_event, apiBase) => {
  return ensureBackend(apiBase);
});

app.whenReady().then(async () => {
  createWindow();
  ensureBackend("http://127.0.0.1:8000").catch(() => {});

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("before-quit", () => {
  stopOwnedBackend();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
