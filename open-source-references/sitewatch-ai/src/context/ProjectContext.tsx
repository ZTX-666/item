import React, { createContext, useContext, useState, ReactNode } from "react";

interface Violation {
  type: string;
  severity: string;
  location: string;
  recommendation: string;
}

interface VisionResult {
  violations: Violation[];
  progress_estimate: number;
  overall_safety_score: number;
  summary: string;
  confidence: number;
}

interface RiskFactor {
  factor: string;
  severity: string;
  probability: number;
}

interface RiskResult {
  delay_probability: number;
  days_behind_schedule: number;
  cost_overrun_risk: number;
  top_risks: RiskFactor[];
  recommended_actions: string[];
  target_end_date: string;
  risk_status: string;
}

interface ProjectContextType {
  visionResults: VisionResult | null;
  riskResults: RiskResult | null;
  projectContext: any;
  setVisionResults: (res: VisionResult) => void;
  setRiskResults: (res: RiskResult) => void;
  setProjectContext: (ctx: any) => void;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const ProjectProvider = ({ children }: { children: ReactNode }) => {
  const [visionResults, setVisionResults] = useState<VisionResult | null>(null);
  const [riskResults, setRiskResults] = useState<RiskResult | null>(null);
  const [projectContext, setProjectContext] = useState<any>(null);

  return (
    <ProjectContext.Provider value={{ 
      visionResults, 
      riskResults, 
      projectContext, 
      setVisionResults, 
      setRiskResults,
      setProjectContext
    }}>
      {children}
    </ProjectContext.Provider>
  );
};

export const useProject = () => {
  const context = useContext(ProjectContext);
  if (context === undefined) {
    throw new Error("useProject must be used within a ProjectProvider");
  }
  return context;
};
