import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

const page = (name: string) => fileURLToPath(new URL(`./${name}.html`, import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./', import.meta.url)) } },
  build: {
    outDir: 'dist',
    sourcemap: true,
    emptyOutDir: true,
    // The workspace shell and U8's three script-free documents (BR5.6, BR9.10): the host
    // serves /privacy and /terms from them, and the maintenance server all three.
    rollupOptions: {
      input: {
        index: page('index'),
        privacy: page('privacy'),
        terms: page('terms'),
        maintenance: page('maintenance'),
      },
    },
  },
});
