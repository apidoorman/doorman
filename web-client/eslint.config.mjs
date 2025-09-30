import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    rules: {
      // Tailor strictness for this project to reduce noise and unblock builds
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-require-imports": "off",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          ignoreRestSiblings: true,
          caughtErrors: "none",
        },
      ],
      // Hooks and Next.js rules to warn instead of error during incremental adoption
      "react-hooks/exhaustive-deps": "warn",
      "@next/next/no-page-custom-font": "off",
      // JSX text convenience
      "react/no-unescaped-entities": "off",
      // Some files use expressions for JSX-only conditions
      "@typescript-eslint/no-unused-expressions": "off",
      // Consistent style like early backend code
      "quotes": ["error", "single", { "avoidEscape": true, "allowTemplateLiterals": true }],
      "semi": ["error", "never"],
    },
    linterOptions: {
      reportUnusedDisableDirectives: true,
    },
  },
  // File-specific overrides
  {
    files: ["src/middleware.ts"],
    rules: {
      "@typescript-eslint/no-unused-vars": "off",
    },
  },
];

export default eslintConfig;
