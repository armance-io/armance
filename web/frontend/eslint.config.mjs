import nextPlugin from "eslint-config-next";
import importPlugin from "eslint-plugin-import";
import reactPlugin from "eslint-plugin-react";
import reactHooksPlugin from "eslint-plugin-react-hooks";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";

export default [
  {
    ignores: [
      "node_modules/**",
      ".next/**",
      "out/**",
      "playwright-report/**",
      "test-results/**",
      "coverage/**",
    ],
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
      import: importPlugin,
    },
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "import/no-cycle": ["error", { maxDepth: 5 }],
      "import/no-restricted-paths": [
        "error",
        {
          zones: [
            {
              target: "src/lib",
              from: "src/components",
              message: "lib/ may not import from components/.",
            },
            {
              target: "src/lib",
              from: "src/app",
              message: "lib/ may not import from app/.",
            },
          ],
        },
      ],
    },
  },
  {
    // I.1 (no string literal in user-visible code) is enforced by the
    // CI grep in `web/scripts/check_web_invariants.sh`, not by ESLint.
    // The react/jsx-no-literals rule mis-fires on aria/data attrs,
    // <style> tag children, and decorative glyphs.
    files: ["src/components/**/*.{ts,tsx}"],
    plugins: {
      react: reactPlugin,
      "react-hooks": reactHooksPlugin,
    },
    settings: {
      react: { version: "detect" },
    },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
];
