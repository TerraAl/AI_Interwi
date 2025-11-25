import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./index.css";
import Interview from "./pages/Interview";
import AdminPanel from "./pages/AdminPanel";

const router = createBrowserRouter([
  { path: "/", element: <Interview /> },
  { path: "/admin", element: <AdminPanel /> },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);

