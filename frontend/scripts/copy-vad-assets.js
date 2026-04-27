const fs = require('fs');
const path = require('path');

const dest = path.join(__dirname, '../public/vad-assets');
fs.mkdirSync(dest, { recursive: true });

const copies = [
  ['@ricky0123/vad-web/dist/vad.worklet.bundle.min.js', 'vad.worklet.bundle.min.js'],
  ['@ricky0123/vad-web/dist/silero_vad_legacy.onnx', 'silero_vad_legacy.onnx'],
  ['onnxruntime-web/dist/ort-wasm-simd-threaded.mjs', 'ort-wasm-simd-threaded.mjs'],
  ['onnxruntime-web/dist/ort-wasm-simd-threaded.wasm', 'ort-wasm-simd-threaded.wasm'],
  ['onnxruntime-web/dist/ort-wasm-simd-threaded.asyncify.mjs', 'ort-wasm-simd-threaded.asyncify.mjs'],
  ['onnxruntime-web/dist/ort-wasm-simd-threaded.asyncify.wasm', 'ort-wasm-simd-threaded.asyncify.wasm'],
];

for (const [src, filename] of copies) {
  const srcPath = require.resolve(src);
  fs.copyFileSync(srcPath, path.join(dest, filename));
  console.log(`✅ Copied ${filename}`);
}