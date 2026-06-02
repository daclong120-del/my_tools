const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

// Fix GPU sandbox crash on some Windows machines
app.commandLine.appendSwitch('no-sandbox');
app.commandLine.appendSwitch('disable-gpu-sandbox');

let mainWindow;
let backendProcess;

// Ensure only one instance of the app is running to prevent cache locking issues
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
  process.exit(0);
}

app.on('second-instance', (event, commandLine, workingDirectory) => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});
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

// Helper to check if backend API is ready via HTTP health endpoint
const http = require('http');
function checkBackendHealth(port, host, timeout = 1000) {
  return new Promise((resolve) => {
    const req = http.get(`http://${host}:${port}/health`, { timeout }, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve(json.status === 'ready');
        } catch {
          resolve(false);
        }
      });
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
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

  const isProd = app.isPackaged;

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
          PYTHONIOENCODING: 'utf-8',
          USER_DATA_PATH: app.getPath('userData')
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
    // Fallback: force-kill by PID if graceful kill didn't work
    if (backendProcess.pid && process.platform === 'win32') {
      try {
        const { execSync } = require('child_process');
        execSync(`taskkill /f /pid ${backendProcess.pid}`, { stdio: 'ignore' });
      } catch (e) {
        // Ignored if process was already terminated
      }
    }
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

// IPC main handlers for download directory management
ipcMain.handle('select-directory', async (event, defaultPath) => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory', 'createDirectory'],
    defaultPath: defaultPath || undefined
  });
  if (result.canceled) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle('show-save-dialog', async (event, options) => {
  const result = await dialog.showSaveDialog(mainWindow, options);
  if (result.canceled) {
    return null;
  }
  return result.filePath;
});

ipcMain.handle('open-directory', async (event, dirPath) => {
  try {
    if (fs.existsSync(dirPath)) {
      await shell.openPath(dirPath);
      return true;
    }
  } catch (e) {
    console.error('Error opening directory:', e);
  }
  return false;
});

