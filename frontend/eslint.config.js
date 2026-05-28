import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import pluginVue from 'eslint-plugin-vue'
import eslintConfigPrettier from 'eslint-config-prettier'
import globals from 'globals'

export default [
  // 1. Global ignores
  {
    ignores: ['dist/**', 'node_modules/**', 'coverage/**', 'public/**'],
  },

  // 2. Base JS recommended rules (no-unused-vars, no-undef, etc.)
  js.configs.recommended,

  // 3. TypeScript recommended rules
  ...tseslint.configs.recommended,

  // 4. Vue 3 recommended rules (flat config format)
  ...pluginVue.configs['flat/recommended'],

  // 5. Browser globals for all source files (window, console, setTimeout, Event, etc.)
  {
    files: ['src/**/*.{ts,tsx,vue,js,jsx}'],
    languageOptions: {
      globals: {
        ...globals.browser,
      },
    },
  },

  // 6. Node globals for config files at project root
  {
    files: ['*.config.{js,ts,mjs,mts}'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },

  // 7. Vue SFC: use typescript-eslint parser inside <script lang="ts">
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser,
      },
    },
  },

  // 8. Custom rules — aligned with tsconfig (noUnusedLocals=false, noUnusedParameters=false)
  {
    rules: {
      // --- TypeScript ---
      '@typescript-eslint/no-unused-vars': [
        'warn',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrorsIgnorePattern: '^_',
        },
      ],
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/no-empty-object-type': 'off',

      // --- Vue ---
      'vue/multi-word-component-names': 'off',
      'vue/no-v-html': 'warn',
      'vue/require-default-prop': 'off',
      'vue/attribute-hyphenation': 'off',
      'vue/v-on-event-hyphenation': 'off',

      // --- General ---
      'no-console': 'off',
      'no-debugger': 'off',
    },
  },

  // 9. Prettier integration — MUST be last to override formatting rules
  eslintConfigPrettier,
]
