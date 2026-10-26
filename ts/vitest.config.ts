import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/**/*.test.{ts,tsx}"],
    // CopilotKit imports its stylesheet; let Vite handle it rather than Node.
    server: { deps: { inline: [/@copilotkit/] } },
  },
});
