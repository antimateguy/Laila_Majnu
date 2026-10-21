import tseslint from "typescript-eslint";

const renderTextOnly = "Chat-derived strings and LLM output render as text only (LLD: Security).";

export default tseslint.config(
  { ignores: ["dist", "src/types/gen.ts"] },
  ...tseslint.configs.strict,
  {
    files: ["**/*.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": [
        "error",
        { selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']", message: renderTextOnly },
        { selector: "MemberExpression[property.name=/^(innerHTML|outerHTML)$/]", message: renderTextOnly },
        { selector: "CallExpression[callee.property.name='insertAdjacentHTML']", message: renderTextOnly },
      ],
      "no-eval": "error",
      "no-implied-eval": "error",
    },
  },
);
