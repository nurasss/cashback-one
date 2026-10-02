import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { host: 'localhost' },
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], clearMocks: true, restoreMocks: true },
});
