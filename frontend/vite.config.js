import { defineConfig } from 'vite';

// Dev-only: suppresses Vite's fullscreen HMR error overlay so a
// pre-existing, unrelated warning (the @ricky0123/vad-web library's
// WASM asset path being flagged by Vite's module-import checker,
// even though it loads fine at runtime via a plain URL string) does
// not block the page. Does not affect the production build or hide
// errors in the terminal/console — only the on-page overlay.
export default defineConfig({
  server: {
    hmr: {
      overlay: false,
    },
  },
});
