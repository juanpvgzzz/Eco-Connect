import { createRoot } from "react-dom/client";
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/poppins/latin-600.css";
import "@fontsource/poppins/latin-700.css";
import "../styles.css";
import { App } from "./App.jsx";
import { ErrorBoundary } from "../components/ErrorBoundary.jsx";
import { ToastProvider } from "../components/ui/Toast.jsx";

createRoot(document.getElementById("root")).render(
  <ErrorBoundary>
    <ToastProvider>
      <App />
    </ToastProvider>
  </ErrorBoundary>,
);
