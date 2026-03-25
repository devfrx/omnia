import './assets/main.css'
import '@fontsource-variable/geist'

import { addCollection } from '@iconify/vue'
import { icons as solarIcons } from '@iconify-json/solar'

// Register Solar icon set locally — no network requests needed.
addCollection(solarIcons)

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
