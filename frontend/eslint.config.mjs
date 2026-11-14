import js from '@eslint/js';
import { defineConfig } from 'eslint/config';
import tseslint from 'typescript-eslint';

export default defineConfig(
  { ignores: ['dist/**', 'node_modules/**', '*.tsbuildinfo'] },
  {
    files: ['src/**/*.{ts,tsx}', 'vite.config.ts'],
    extends: [js.configs.recommended, tseslint.configs.recommended],
    rules: {
      // TypeScript already resolves globals, with DOM types configured in tsconfig.
      'no-undef': 'off',
      // A deliberately empty logout catch must not block clearing local session.
      'no-empty': 'off',
    },
  },
);
