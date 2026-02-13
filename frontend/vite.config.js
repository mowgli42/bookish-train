import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  server: {
    host: true,
    proxy: {
      '/api': process.env.VITE_PROXY_API || 'http://localhost:8000',
    },
  },
})
