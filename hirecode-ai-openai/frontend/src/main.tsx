import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";
import "./index.css";
import Login from "./pages/Login";
import Interview from "./pages/Interview";
import AdminPanel from "./pages/AdminPanel";

const router = createBrowserRouter(
  [
    { path: "/", element: <Login /> },
    { path: "/login", element: <Login /> },
    { path: "/interview", element: <Interview /> },
    { path: "/admin", element: <AdminPanel /> },
    { path: "*", element: <Navigate to="/" replace /> },
  ],
  { basename: "/" }
);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);

