import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { errorMessage, fetchHealth } from "./api";
import RunDetailPage from "./pages/RunDetailPage";
import RunsPage from "./pages/RunsPage";
import SummaryPage from "./pages/SummaryPage";
import UploadPage from "./pages/UploadPage";
import "./App.css";

export default function App() {
  const [health, setHealth] = useState<"loading" | "ok" | "error">("loading");
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then(() => {
        if (!cancelled) {
          setHealth("ok");
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setHealth("error");
          setHealthError(errorMessage(error));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <header className="topbar">
        <NavLink to="/" className="brand">
          TrajectoryLens
        </NavLink>
        <nav>
          <NavLink to="/" end>
            Runs
          </NavLink>
          <NavLink to="/summary">Summary</NavLink>
          <NavLink to="/upload">Upload</NavLink>
        </nav>
        <p className={health === "error" ? "health error" : "health"}>
          {health === "loading" ? "Checking API…" : null}
          {health === "ok" ? "API ok" : null}
          {health === "error" ? healthError : null}
        </p>
      </header>
      <Routes>
        <Route path="/" element={<RunsPage />} />
        <Route path="/runs/:runId" element={<RunDetailPage />} />
        <Route path="/summary" element={<SummaryPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="*" element={<RunsPage />} />
      </Routes>
    </>
  );
}
