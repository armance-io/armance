import nextPlugin from "eslint-config-next";
import importPlugin from "eslint-plugin-import";
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
    files: ["src/components/**/*.{ts,tsx}"],
    rules: {
      "react/jsx-no-literals": [
        "warn",
        {
          noStrings: true,
          ignoreProps: false,
          allowedStrings: ["·", "❦", "—", "→", "↗"],
        },
      ],
    },
  },
];
