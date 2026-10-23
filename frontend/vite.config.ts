import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  base: './',
  define: {
    'process.env.NODE_ENV': '"production"'
  },
  plugins: [vue(), tailwindcss()],
  build: {
    outDir: '../web',
    emptyOutDir: true,
    cssCodeSplit: false,
    lib: {
      entry: 'src/main.ts',
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
