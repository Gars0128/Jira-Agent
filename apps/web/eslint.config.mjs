import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTypescript,
  {
    rules: {
      // `x!` hides a missing value; narrow it (if/early return) or return the value from where it was checked.
      "@typescript-eslint/no-non-null-assertion": "error",
    },
  },
  {
    files: ["app/**/*.tsx"],
    rules: {
      "no-restricted-syntax": ["error", {
        selector: "CallExpression[callee.name='setTimeout'], CallExpression[callee.property.name='setTimeout']",
        message: "Don't wait for React with setTimeout. Do the work in a useEffect that depends on the state that makes it possible (e.g. the element now rendered).",
      }],
    },
  },
  globalIgnores([".next/**", "next-env.d.ts"]),
]);
