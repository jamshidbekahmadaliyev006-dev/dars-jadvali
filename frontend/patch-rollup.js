import fs from 'fs';
import path from 'path';

const nativeJsPath = path.resolve('node_modules/rollup/dist/native.js');

if (fs.existsSync(nativeJsPath)) {
  let content = fs.readFileSync(nativeJsPath, 'utf8');
  if (!content.includes('@rollup/wasm-node/dist/native.js')) {
    content = content.replace(
      'const nativeModule = requireWithFriendlyError(',
      `let nativeModule;
try {
  nativeModule = require('@rollup/wasm-node/dist/native.js');
} catch {
  nativeModule = requireWithFriendlyError(`
    );
    content = content.replace(');', ');\n}');
    fs.writeFileSync(nativeJsPath, content, 'utf8');
    console.log('[UniNotify] Successfully patched Rollup with WebAssembly fallback.');
  }
}
