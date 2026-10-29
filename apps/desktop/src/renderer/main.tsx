import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/source-sans-3/400.css";
import "@fontsource/source-sans-3/500.css";
import "@fontsource/source-sans-3/600.css";
import "@fontsource/source-serif-4/500.css";
import "@fontsource/source-serif-4/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "./styles.css";
import { App } from "./App";
import { I18nProvider } from "./i18n";
import { ProjectProvider } from "./state";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <ProjectProvider>
        <App />
      </ProjectProvider>
    </I18nProvider>
  </StrictMode>,
);
