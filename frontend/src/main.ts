import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './assets/main.css'

import '@fontsource/geist-sans/400.css'
import '@fontsource/geist-sans/500.css'
import '@fontsource/geist-sans/600.css'
import '@fontsource/geist-sans/700.css'
import '@fontsource/geist-mono/400.css'
import '@fontsource/geist-mono/500.css'

const app = createApp(App)
const pinia = createPinia()

// ── 全局兜底错误处理 ──
// 捕获 onErrorCaptured 无法拦截的 app 级错误:
// 插件安装错误、app 级 mixin 错误等。
// 大部分运行时错误已由 App.vue 的 onErrorCaptured 处理,
// 这里仅做最后的 console 兜底, 防止静默吞错。
app.config.errorHandler = (err, _instance, info) => {
  console.error(
    '[GlobalErrorHandler] app 级别错误:\n',
    '  来源:',
    info,
    '\n',
    '  错误:',
    (err as Error).message
  )
}

// ── 未捕获的 Promise rejection 兜底 ──
// 防止 unhandledrejection 导致浏览器弹错误通知
window.addEventListener('unhandledrejection', (event) => {
  console.error('[GlobalErrorHandler] 未处理的 Promise 拒绝:', event.reason)
})

app.use(pinia)
app.use(router)
app.mount('#app')
