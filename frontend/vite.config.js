import { defineConfig } from "vite";
export default defineConfig({
  // Sin @vitejs/plugin-react, esbuild usa por defecto el runtime JSX clásico
  // (React.createElement). El runtime automático importa react/jsx-runtime en
  // cada módulo y evita "React is not defined".
  esbuild: {
    jsx: "automatic",
    jsxImportSource: "react",
  },
  server: {
    proxy: Object.fromEntries(
      ["/accounts", "/community", "/recolecciones", "/content"].map((path) => [
        path,
        {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
          configure(proxy) {
            proxy.on("error", (_error, _request, response) => {
              if (response.headersSent) return;
              response.writeHead(502, { "Content-Type": "application/json" });
              response.end(JSON.stringify({ detail: "FastAPI no está disponible en http://127.0.0.1:8000." }));
            });
          },
        },
      ]),
    ),
  },
});
