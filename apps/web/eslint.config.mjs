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
  globalIgnores([".next/**", "next-env.d.ts"]),
]);
