import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "./app/App";
import "./design-system/tokens.css";
import "./styles.css";

const root = document.getElementById("root");

if (root === null) {
  throw new Error("HAMOON_ROOT_NOT_FOUND");
}

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
