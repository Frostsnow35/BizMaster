/**
 * @brief Electron 预加载脚本
 * 
 * 通过 contextBridge 安全暴露 API 给渲染进程。
 */

const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  isElectron: true,
  platform: process.platform,
  backendUrl: 'http://127.0.0.1:8000',
});
