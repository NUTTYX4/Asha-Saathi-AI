import { Component, type ReactNode, StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";

import App from "./app/App";
import { isV2Path } from "./app/route";
import "./styles/index.css";

// /v2 is the ASHA SAATHI 2.0 app (V2 backend, login required); everything else is the
// unchanged Round 1 voice screen. V2 is a separate chunk, so Round 1 does not load it.
const V2App = lazy(() => import("./app/V2App"));
const isV2 = isV2Path(window.location.pathname);

class LoadBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? (
      <p role="alert" className="p-4">
        The app could not load. Check the connection and reload the page.
      </p>
    ) : (
      this.props.children
    );
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {isV2 ? (
      <LoadBoundary>
        <Suspense fallback={<p className="p-4">Loading…</p>}>
          <V2App />
        </Suspense>
      </LoadBoundary>
    ) : (
      <App />
    )}
  </StrictMode>,
);
