import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@frontend': fileURLToPath(new URL('./src/astrophotoflow/frontend', import.meta.url)) } },
  cacheDir: '.artifacts/cache/vite',
  test: {
    environment: 'jsdom',
    include: ['tests/frontend/**/*.test.ts']
  }
})
