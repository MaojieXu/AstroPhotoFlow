import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@ui': fileURLToPath(new URL('./src', import.meta.url)) } },
  cacheDir: '../../../.artifacts/cache/vite/astrophotoflow-ui',
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.ts']
  }
})
