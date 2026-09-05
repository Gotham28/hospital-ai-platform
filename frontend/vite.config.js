import { defineConfig } from 'vite';

// Dev-only: suppresses Vite's fullscreen HMR error overlay, which would
// otherwise cover the page with a crash screen on every load.
//
// The underlying error is a hard HTTP 500, not a warning. Vite's dev server
// refuses to serve /public files when the app loads them via a dynamic
// import(): it won't transform public-dir files as ES modules (.mjs), and it
// doesn't support native ESM-WebAssembly imports (.wasm). That is exactly how
// @ricky0123/vad-web's onnxruntime-web backend loads its WASM assets, so VAD
// never finishes initializing under `npm run dev` — the mic is a no-op there.
// (A plain fetch() of the same URL returns 200, which is why this looked like
// a benign warning rather than a real failure.)
//
// This is dev-server-only: confirmed working against `vite preview` and in
// production. `overlay: false` only hides the on-page crash screen — it does
// not fix the underlying failure, and does not affect the production build.
// To verify voice/VAD locally, use `npm run build && npm run preview`
// instead of `npm run dev`.
export default defineConfig({
  server: {
    hmr: {
      overlay: false,
    },
  },
  test: {
    environment: 'jsdom',
  },
});
