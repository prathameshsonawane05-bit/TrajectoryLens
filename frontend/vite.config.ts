import react from "@vitejs/plugin-react";
import { defineConfig, type ProxyOptions } from "vite";

const bypassHtml: ProxyOptions["bypass"] = (request) => {
  const accept = request.headers.accept;
  const header = Array.isArray(accept) ? accept.join(",") : (accept ?? "");
  if (header.includes("text/html")) {
    return "/index.html";
  }
};

const apiProxy = {
  target: "http://127.0.0.1:8000",
  changeOrigin: true,
};

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/health": apiProxy,
      "/summary": {
        ...apiProxy,
        bypass: bypassHtml,
      },
      "/runs": {
        ...apiProxy,
        bypass: bypassHtml,
      },
    },
  },
});
