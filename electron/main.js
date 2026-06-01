const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

// Disable hardware acceleration to prevent GPU crashes on systems with missing/incompatible graphics drivers
app.disableHardwareAcceleration();
app.commandLine.appendSwitch('disable-gpu');
app.commandLine.appendSwitch('disable-software-rasterizer');
app.commandLine.appendSwitch('disable-gpu-sandbox');
app.commandLine.appendSwitch('no-sandbox');

// Helper to get log path lazily
function getLogPath(filename) {
  try {
    const userData = app.getPath('userData');
    fs.mkdirSync(userData, { recursive: true });
    return path.join(userData, filename);
  } catch (e) {
    return null;
  }
}

// Log main process errors to file
process.on('uncaughtException', (error) => {
  try {
    const logPath = getLogPath('main-error.log');
    if (logPath) {
      fs.appendFileSync(logPath, `[Uncaught Exception] ${new Date().toISOString()}:\n${error.stack || error}\n\n`);
    }
  } catch (e) {}
  app.quit();
});

process.on('unhandledRejection', (reason, promise) => {
  try {
    const logPath = getLogPath('main-error.log');
    if (logPath) {
      fs.appendFileSync(logPath, `[Unhandled Rejection] ${new Date().toISOString()}:\n${reason.stack || reason}\n\n`);
    }
  } catch (e) {}
});

let mainWindow;
let backendProcess;

// Helper to check if TCP port is active
const net = require('net');
function checkPortStatus(port, host, timeout = 500) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    let status = false;

    socket.setTimeout(timeout);
    
    socket.on('connect', () => {
      status = true;
      socket.destroy();
    });

    socket.on('timeout', () => {
      socket.destroy();
    });

    socket.on('error', () => {
      socket.destroy();
    });

    socket.on('close', () => {
      resolve(status);
    });

    socket.connect(port, host);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  // Log renderer errors and crashes
  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
    try {
      const logPath = getLogPath('main-error.log');
      if (logPath) {
        fs.appendFileSync(logPath, `[Renderer Fail Load] ${validatedURL}: ${errorDescription} (${errorCode})\n`);
      }
    } catch (e) {}
  });

  mainWindow.webContents.on('render-process-gone', (event, details) => {
    try {
      const logPath = getLogPath('main-error.log');
      if (logPath) {
        fs.appendFileSync(logPath, `[Renderer Process Gone] Reason: ${details.reason}, ExitCode: ${details.exitCode}\n`);
      }
    } catch (e) {}
  });

  // Load beautiful loading screen first
  mainWindow.loadURL('data:text/html,<html><head><meta charset="utf-8"><style>body{display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background-color:#0f0f15;color:#ffffff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;} .container{text-align:center;} .spinner{border:4px solid rgba(255,255,255,0.1);width:40px;height:40px;border-radius:50%;border-left-color:#3b82f6;animation:spin 1s linear infinite;margin:0 auto 20px;} @keyframes spin{0%{transform:rotate(0deg);}100%{transform:rotate(360deg);}} h2{font-weight:500;margin:0 0 10px 0;letter-spacing:-0.01em;} p{color:#9ca3af;margin:0;font-size:14px;}</style></head><body><div class="container"><div class="spinner"></div><h2>Khởi động Engine gỡ lỗi...</h2><p>Đang kết nối tới Python Backend API</p></div></body></html>');

  const isProd = app.isPackaged;
  const port = 8003;

  async function loadApplication() {
    let retries = 40; // Wait up to 20 seconds (40 * 500ms)
    while (retries > 0) {
      const active = await checkPortStatus(port, '127.0.0.1');
      if (active) break;
      await new Promise(r => setTimeout(r, 500));
      retries--;
    }

    if (isProd) {
      mainWindow.loadFile(path.join(__dirname, 'frontend/index.html'))
        .catch(() => {
          mainWindow.loadURL('data:text/html,<h1>MyTools Desktop</h1><p>Frontend static files not found. Please run build scripts first.</p>');
        });
    } else {
      mainWindow.loadURL('http://localhost:3000')
        .catch(() => {
          const indexPath = path.join(__dirname, '../frontends/socialpeta_downloader/out/index.html');
          mainWindow.loadFile(indexPath).catch(() => {
            mainWindow.loadURL('data:text/html,<h1>MyTools Desktop</h1><p>Please run next.js dev server on http://localhost:3000 or build static files.</p>');
          });
        });
    }
  }

  loadApplication();

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

function startBackend() {
  // Spawn Python backend
  const isProd = app.isPackaged;
  if (isProd) {
    const backendPath = path.join(process.resourcesPath, 'api.exe');
    const logPath = getLogPath('backend.log');
    let logFd;
    try {
      if (logPath) {
        logFd = fs.openSync(logPath, 'a');
        fs.writeSync(logFd, `\n[Spawn] Starting backend at ${new Date().toISOString()}\n`);
      }
    } catch (e) {
      console.error('Failed to open backend log file:', e);
    }

    try {
      backendProcess = spawn(backendPath, [], {
        cwd: process.resourcesPath,
        stdio: logFd !== undefined ? ['ignore', logFd, logFd] : 'ignore',
        windowsHide: true,
        shell: false,
        env: {
          ...process.env,
          PYTHONUTF8: '1',
          PYTHONIOENCODING: 'utf-8'
        }
      });

      backendProcess.on('error', (err) => {
        try {
          const logPath = getLogPath('main-error.log');
          if (logPath) {
            fs.appendFileSync(logPath, `[Backend Process Error] ${new Date().toISOString()}:\n${err.stack || err}\n\n`);
          }
        } catch (e) {}
      });
    } catch (err) {
      console.error('Failed to start backend process:', err);
      try {
        const logPath = getLogPath('main-error.log');
        if (logPath) {
          fs.appendFileSync(logPath, `[Backend Spawn Catch] ${new Date().toISOString()}:\n${err.stack || err}\n\n`);
        }
      } catch (e) {}
    }
  }
}

app.on('ready', () => {
  startBackend();
  createWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('quit', () => {
  if (backendProcess) {
    try {
      backendProcess.kill();
    } catch (e) {}
  }
  if (process.platform === 'win32') {
    try {
      const { execSync } = require('child_process');
      execSync('taskkill /f /im api.exe');
    } catch (e) {
      // Ignored if process was already terminated
    }
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});
