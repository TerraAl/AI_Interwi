import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./index.css";
import Login from "./pages/Login";
import Interview from "./pages/Interview";
import AdminPanel from "./pages/AdminPanel";

const router = createBrowserRouter([
  { path: "/", element: <Login /> },
  { path: "/interview", element: <Interview /> },
  { path: "/admin", element: <AdminPanel /> },
  { path: "*", element: <Login /> },  // Catch-all: redirect to Login
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);

