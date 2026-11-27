import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({ plugins: [react(), tailwindcss()], server: { proxy: { '/ppt-agent': 'http://127.0.0.1:8000' } }, resolve: { alias: { '@': new URL('./src', import.meta.url).pathname.replace(/^\/(\w:)/, '$1') } } })
