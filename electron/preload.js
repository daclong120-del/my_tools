// All of the Node.js APIs are available in the preload process.
// It has the same sandbox as a Chrome extension.
const { contextBridge, ipcRenderer } = require('electron');

window.addEventListener('DOMContentLoaded', () => {
  const replaceText = (selector, text) => {
    const element = document.getElementById(selector);
    if (element) element.innerText = text;
  };

  for (const type of ['chrome', 'node', 'electron']) {
    replaceText(`${type}-version`, process.versions[type]);
  }
});

contextBridge.exposeInMainWorld('electronAPI', {
  selectDirectory: (defaultPath) => ipcRenderer.invoke('select-directory', defaultPath),
  showSaveDialog: (options) => ipcRenderer.invoke('show-save-dialog', options),
  openDirectory: (dirPath) => ipcRenderer.invoke('open-directory', dirPath)
});

