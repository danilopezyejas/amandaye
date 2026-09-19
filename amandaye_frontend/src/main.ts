import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { RouterView } from 'vue-router'
import router from './router'
import './style.css'

const app = createApp(RouterView)
const pinia = createPinia()

app.use(pinia)
app.use(router)

app.mount('#app')
