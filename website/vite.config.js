import { defineConfig } from 'vite'

export default defineConfig({
  base: '/EHR-Code-Mapper/',
  build: {
    outDir: '../docs',
    emptyOutDir: true,
  }
})
