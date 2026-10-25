import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  base: './',
  resolve: { alias: { '@frontend': fileURLToPath(new URL('./src/astrophotoflow/frontend', import.meta.url)) } },
  define: {
    'process.env.NODE_ENV': '"production"'
  },
  plugins: [vue(), tailwindcss()],
  build: {
    outDir: 'build/frontend',
    emptyOutDir: true,
    cssCodeSplit: false,
    lib: {
      entry: 'src/astrophotoflow/frontend/main.ts',
      name: 'AstroPhotoFlow',
      formats: ['es'],
      fileName: () => 'astrophotoflow.js',
      cssFileName: 'astrophotoflow'
    },
    rollupOptions: {
      external: ['../../scripts/app.js', '../../../scripts/api.js'],
      output: { paths: { '../../scripts/app.js': '/scripts/app.js', '../../../scripts/api.js': '/scripts/api.js' } }
    }
  }
})
