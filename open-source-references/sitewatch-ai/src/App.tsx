/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import Dashboard from "./pages/Dashboard";
import UploadCenter from "./pages/UploadCenter";
import RiskAnalytics from "./pages/RiskAnalytics";
import ReportsPage from "./pages/ReportsPage";
import Layout from "./components/layout/Layout";
import { Toaster } from "@/components/ui/sonner";
import { ProjectProvider } from "./context/ProjectContext";

export default function App() {
  return (
    <ProjectProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<LandingPage />} />

          {/* Protected Routes (Authenticated/Dashboard) */}
          <Route path="/dashboard" element={<Layout><Dashboard /></Layout>} />
          <Route path="/upload" element={<Layout><UploadCenter /></Layout>} />
          <Route path="/risk" element={<Layout><RiskAnalytics /></Layout>} />
          <Route path="/reports" element={<Layout><ReportsPage /></Layout>} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Toaster position="top-right" theme="dark" />
      </BrowserRouter>
    </ProjectProvider>
  );
}

