import axios from 'axios'

const client = axios.create({
  // 开发模式走 Vite 代理；Electron 生产模式以 file:// 加载，需使用绝对地址
  baseURL: import.meta.env.DEV ? '/api' : 'http://127.0.0.1:8000/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

export default client
