const { app, BrowserWindow, ipcMain } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");
const fs = require("fs");

let backendProcess = null;
let backendPort = null;
let backendLogLines = [];

function rememberBackendLog(line) {
  const text = String(line || "").trim();
  if (!text) {
    return;
  }
  backendLogLines.push(`[${new Date().toLocaleTimeString()}] ${text}`);
  if (backendLogLines.length > 80) {
    backendLogLines = backendLogLines.slice(-80);
  }
}

function getBackendLogs() {
  return backendLogLines.slice();
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 960,
    minHeight: 680,
    title: "投标",
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
        path: "/health",
        timeout: 2500
      },
      (response) => {
        let body = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          body += chunk;
        });
        response.on("end", () => {
          if (response.statusCode < 200 || response.statusCode >= 500) {
            resolve(false);
            return;
          }
          try {
            const data = JSON.parse(body || "{}");
            resolve(data.status === "ok" || response.statusCode < 500);
          } catch {
            resolve(response.statusCode >= 200 && response.statusCode < 500);
          }
        });
      }
    );
    request.on("timeout", () => {
      request.destroy();
      resolve(false);
    });
    request.on("error", () => resolve(false));
  });
}

async function waitForBackend(port, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await checkBackend(port)) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
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
    return { port, status: "running", logs: getBackendLogs() };
  }

  if (await checkBackend(port)) {
    stopOwnedBackend();
    backendPort = port;
    rememberBackendLog(`Detected existing backend on port ${port}.`);
    return { port, status: "external-running", logs: getBackendLogs() };
  }

  if (backendPort !== port) {
    stopOwnedBackend();
  }

  const backendDir = findBackendDirectory();
  const pythonExecutable = process.env.PYTHON || "python";
  backendLogLines = [];
  rememberBackendLog(`Starting backend: ${pythonExecutable} -m uvicorn bid_parser_api:app --host 127.0.0.1 --port ${port}`);
  rememberBackendLog(`Backend cwd: ${backendDir}`);

  backendProcess = spawn(
    pythonExecutable,
    ["-m", "uvicorn", "bid_parser_api:app", "--host", "127.0.0.1", "--port", String(port)],
    {
      cwd: backendDir,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
      detached: false
    }
  );
  backendPort = port;

  backendProcess.stdout.on("data", (data) => rememberBackendLog(data.toString()));
  backendProcess.stderr.on("data", (data) => rememberBackendLog(data.toString()));
  backendProcess.on("error", (error) => {
    rememberBackendLog(`Backend process error: ${error.message}`);
  });
  backendProcess.on("exit", (code, signal) => {
    rememberBackendLog(`Backend exited. code=${code ?? ""} signal=${signal ?? ""}`);
    backendProcess = null;
    backendPort = null;
  });

  const ok = await waitForBackend(port);
  if (!ok) {
    const logs = getBackendLogs().slice(-20).join("\n") || "无后端日志。";
    stopOwnedBackend();
    throw new Error(`后端启动或连接失败：30 秒内未通过 /health 检查。\n端口：${port}\n后端目录：${backendDir}\n\n最近日志：\n${logs}`);
  }

  return { port, status: "started", backendDir, logs: getBackendLogs() };
}

async function diagnoseBackend(apiBase) {
  const { port } = parseBackendTarget(apiBase);
  let backendDir = "";
  try {
    backendDir = findBackendDirectory();
  } catch (error) {
    backendDir = `未找到：${error.message}`;
  }
  return {
    port,
    healthy: await checkBackend(port),
    ownedProcess: Boolean(backendProcess),
    backendDir,
    logs: getBackendLogs()
  };
}

ipcMain.handle("backend:ensure", async (_event, apiBase) => {
  return ensureBackend(apiBase);
});

ipcMain.handle("backend:diagnose", async (_event, apiBase) => {
  return diagnoseBackend(apiBase);
});

app.whenReady().then(async () => {
  createWindow();
  ensureBackend("http://127.0.0.1:8000").catch((error) => {
    rememberBackendLog(`Initial backend ensure failed: ${error.message}`);
  });

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
