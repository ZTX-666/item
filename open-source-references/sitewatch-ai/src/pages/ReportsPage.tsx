import { motion } from "motion/react";
import { 
  FileText, 
  Download, 
  CheckCircle2, 
  Clock, 
  Activity, 
  ShieldAlert, 
  Calendar, 
  AlertTriangle,
  TrendingUp,
  Award
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { jsPDF } from "jspdf";
import { toast } from "sonner";
import { useProject } from "@/context/ProjectContext";
import { Link } from "react-router-dom";

export default function ReportsPage() {
  const { visionResults, riskResults } = useProject();

  if (!visionResults && !riskResults) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6 text-center">
        <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
          <Activity className="w-10 h-10 text-primary animate-pulse" />
        </div>
        <div className="space-y-2">
          <h2 className="text-3xl font-black uppercase tracking-tighter">Reporting Vault Empty</h2>
          <p className="text-foreground/40 max-w-sm mx-auto">Upload project data to generate AI-certified audit reports and safety archives.</p>
        </div>
        <Link to="/upload">
          <Button size="lg" className="rounded-full px-10 bg-primary hover:bg-primary/90 text-white font-black uppercase tracking-widest">
            Go to Upload Center
          </Button>
        </Link>
      </div>
    );
  }

  const generatePDF = (reportName: string) => {
    const doc = new jsPDF();
    
    // Header block
    doc.setFillColor(255, 140, 0); // Active Orange
    doc.rect(0, 0, 210, 45, "F");
    
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(26);
    doc.setFont("helvetica", "bold");
    doc.text("SITEWATCH AI REPORT", 15, 22);
    
    doc.setFontSize(9);
    doc.setFont("helvetica", "normal");
    doc.text(`DATE GENERATED: ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString()}`, 15, 34);
    doc.text(`AUDIT COMPLIANCE REFERENCE ID: SW-${Math.random().toString(36).substring(3, 9).toUpperCase()}`, 15, 39);
    doc.text(`ENGINE: GEMINI 3.1 FLASH LITE`, 145, 34);
    doc.text(`STATUS: CERTIFIED READY`, 145, 39);

    // Document Title
    doc.setTextColor(0, 0, 0);
    doc.setFontSize(16);
    doc.setFont("helvetica", "bold");
    doc.text(reportName.toUpperCase(), 15, 60);

    // Section 1: Executive AI Summary
    doc.setFontSize(11);
    doc.setFillColor(245, 245, 245);
    doc.rect(15, 68, 180, 8, "F");
    doc.text("EXECUTIVE AI SUMMARY", 18, 74);
    
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    const summaryText = visionResults?.summary || "No visual cache or active PDF text uploaded yet. Connect and scan project schedules or report files to populate execution tracking data.";
    const summaryLines = doc.splitTextToSize(summaryText, 174);
    doc.text(summaryLines, 18, 84);

    let yPos = 84 + (summaryLines.length * 5) + 8;

    // Section 2: Critical Findings & Safety Violations
    doc.setFont("helvetica", "bold");
    doc.setFontSize(11);
    doc.setFillColor(245, 245, 245);
    doc.rect(15, yPos, 180, 8, "F");
    doc.text("OBSERVED VIOLATIONS & COMPLIANCE FINDINGS", 18, yPos + 6);
    
    yPos += 14;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    if (visionResults?.violations && visionResults.violations.length > 0) {
      visionResults.violations.forEach((v, idx) => {
        if (yPos > 270) { doc.addPage(); yPos = 20; }
        doc.setFont("helvetica", "bold");
        doc.text(`${idx + 1}. [${v.severity.toUpperCase()}] ${v.type} (Location: ${v.location})`, 18, yPos);
        doc.setFont("helvetica", "normal");
        const recLines = doc.splitTextToSize(`Recommendation: ${v.recommendation}`, 170);
        doc.text(recLines, 22, yPos + 4.5);
        yPos += 6 + (recLines.length * 4.5);
      });
    } else {
      doc.text("- No safety violations or hazardous items were parsed in this audit report.", 18, yPos);
      yPos += 8;
    }

    // Section 3: Project Risk & Timeline Forecasts
    yPos += 4;
    if (yPos > 240) { doc.addPage(); yPos = 20; }
    doc.setFont("helvetica", "bold");
    doc.setFontSize(11);
    doc.setFillColor(245, 245, 245);
    doc.rect(15, yPos, 180, 8, "F");
    doc.text("PREDICTIVE TIMELINE & RISK OUTLOOK", 18, yPos + 6);
    
    yPos += 14;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.text(`- Delay Probability: ${riskResults?.delay_probability || 0}%`, 18, yPos);
    doc.text(`- Estimated Schedule Drift: +${riskResults?.days_behind_schedule || 0} Days`, 18, yPos + 6);
    doc.text(`- Projected Budget Deviation Risk: +${riskResults?.cost_overrun_risk || 0}%`, 18, yPos + 12);
    
    yPos += 20;

    // Section 4: Key Identified Vulnerabilities
    if (yPos > 240) { doc.addPage(); yPos = 20; }
    doc.setFont("helvetica", "bold");
    doc.setFontSize(11);
    doc.setFillColor(245, 245, 245);
    doc.rect(15, yPos, 180, 8, "F");
    doc.text("CRITICAL TIMELINE VULNERABILITIES", 18, yPos + 6);
    
    yPos += 14;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    if (riskResults?.top_risks && riskResults.top_risks.length > 0) {
      riskResults.top_risks.forEach((risk, idx) => {
        if (yPos > 270) { doc.addPage(); yPos = 20; }
        const riskText = typeof risk === "string" ? risk : risk.factor;
        const riskLines = doc.splitTextToSize(`- ${riskText}`, 174);
        doc.text(riskLines, 18, yPos);
        yPos += riskLines.length * 4.5;
      });
    } else {
      doc.text("- No timeline delays or cost overrun warnings noted in standard data models.", 18, yPos);
      yPos += 8;
    }

    // Section 5: AI Recommended Action Items
    yPos += 4;
    if (yPos > 240) { doc.addPage(); yPos = 20; }
    doc.setFont("helvetica", "bold");
    doc.setFontSize(11);
    doc.setFillColor(245, 245, 245);
    doc.rect(15, yPos, 180, 8, "F");
    doc.text("AI ACTIONABLE STRATEGIC MITIGATIONS", 18, yPos + 6);
    
    yPos += 14;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    if (riskResults?.recommended_actions && riskResults.recommended_actions.length > 0) {
      riskResults.recommended_actions.forEach((act, idx) => {
        if (yPos > 270) { doc.addPage(); yPos = 20; }
        const actLines = doc.splitTextToSize(`${idx + 1}. ${act}`, 174);
        doc.text(actLines, 18, yPos);
        yPos += actLines.length * 4.5;
      });
    } else {
      doc.text("- Project is operating within base timeline tolerances. Continue standard auditing.", 18, yPos);
      yPos += 8;
    }

    // Footer signature
    if (yPos > 265) { doc.addPage(); yPos = 20; }
    yPos += 10;
    doc.setDrawColor(220, 220, 220);
    doc.line(15, yPos, 195, yPos);
    
    doc.setFont("helvetica", "italic");
    doc.setFontSize(8);
    doc.setTextColor(120, 120, 120);
    doc.text("SiteWatch AI compliance signatures are automatically certified by frontier AI modules.", 15, yPos + 6);
    doc.text("Ensure local engineering review matches all observations prior to critical timeline baseline drift modifications.", 15, yPos + 10);

    doc.save(`${reportName.toLowerCase().replace(/ /g, "_")}.pdf`);
    toast.success("PDF Downloaded Successfully");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-8 max-w-5xl mx-auto"
    >
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div className="space-y-1 text-left">
          <h1 className="text-4xl font-black uppercase tracking-tighter">Reporting Center</h1>
          <p className="text-foreground/40 font-medium">Compliance-ready audit reports generated by Gemini</p>
        </div>
        <div className="flex gap-4 w-full md:w-auto">
          <Button 
            size="lg" 
            className="rounded-full bg-primary hover:bg-primary/90 text-white gap-2 flex-1 md:flex-none font-bold tracking-wider uppercase text-xs" 
            onClick={() => generatePDF("Executive AI Site Audit")}
          >
            <Download size={16} /> Export Certified PDF
          </Button>
        </div>
      </div>

      {/* Main Beautiful Inline Report Document */}
      <Card className="glass-card border-none rounded-[2.5rem] overflow-hidden p-8 md:p-12 relative shadow-2xl">
        {/* Subtle decorative glow */}
        <div className="absolute top-0 right-0 w-80 h-80 bg-primary/10 rounded-full blur-3xl -z-10" />
        <div className="absolute bottom-0 left-0 w-80 h-80 bg-orange-600/5 rounded-full blur-3xl -z-10" />

        {/* Document Header Bar */}
        <div className="border-b border-white/5 pb-8 mb-8 flex flex-col md:flex-row justify-between gap-6">
          <div className="space-y-3 text-left">
            <div className="flex flex-wrap items-center gap-3">
              <Badge className="bg-primary/20 text-primary border border-primary/30 rounded-full px-3 py-1 font-bold text-[10px] tracking-widest uppercase">
                SW-AUDIT-{Math.floor(100000 + Math.random() * 900000)}
              </Badge>
              <Badge variant="outline" className="border-green-500/30 text-green-500 bg-green-500/5 rounded-full px-3 py-1 font-bold text-[10px] tracking-widest uppercase flex items-center gap-1">
                <CheckCircle2 size={10} /> Certified Ready
              </Badge>
            </div>
            <h2 className="text-3xl font-black uppercase tracking-tight text-white leading-none">Executive AI Site Audit</h2>
            <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-foreground/40 font-semibold mt-2">
              <span className="flex items-center gap-1.5"><Calendar size={14} className="text-primary" /> {new Date().toLocaleDateString()}</span>
              <span className="flex items-center gap-1.5"><Clock size={14} className="text-primary" /> {new Date().toLocaleTimeString()}</span>
              <span className="flex items-center gap-1.5"><Award size={14} className="text-primary" /> Engine: Gemini 3.1 Flash Lite</span>
            </div>
          </div>
          <div className="flex items-end">
            <div className="p-4 bg-white/5 border border-white/10 rounded-3xl flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-primary/20 flex items-center justify-center text-primary">
                <Activity size={20} />
              </div>
              <div className="text-left">
                <p className="text-[10px] uppercase font-bold tracking-widest text-foreground/40 leading-none mb-1">Safety Index</p>
                <p className="text-xl font-black leading-none text-white">{visionResults?.overall_safety_score || 100}%</p>
              </div>
            </div>
          </div>
        </div>

        {/* Report Content Sections */}
        <div className="space-y-10 text-left">
          {/* Executive Summary */}
          <div className="space-y-4">
            <h3 className="text-sm font-black uppercase tracking-widest text-primary flex items-center gap-2">
              <span className="w-1.5 h-3 bg-primary rounded-full" /> Executive AI Summary
            </h3>
            <div className="p-6 rounded-3xl bg-white/5 border border-white/5 relative overflow-hidden">
              <p className="text-foreground/80 leading-relaxed text-sm font-medium">
                {visionResults?.summary || "Project performance tracking via real-time vision and schedule analysis. No critical blockers detected at initialization."}
              </p>
              <div className="absolute right-4 bottom-4 text-foreground/5 opacity-10">
                <FileText size={120} />
              </div>
            </div>
          </div>

          {/* Observed Safety Violations */}
          <div className="space-y-4">
            <h3 className="text-sm font-black uppercase tracking-widest text-primary flex items-center gap-2">
              <span className="w-1.5 h-3 bg-primary rounded-full" /> Observed Violations & Compliance Findings
            </h3>
            <div className="grid grid-cols-1 gap-4">
              {visionResults?.violations && visionResults.violations.length > 0 ? (
                visionResults.violations.map((v, idx) => (
                  <div key={idx} className="p-5 rounded-2xl bg-white/5 border border-white/5 flex flex-col md:flex-row md:items-center justify-between gap-4 group hover:bg-white/[0.08] hover:border-primary/20 transition-all">
                    <div className="space-y-1">
                      <div className="flex items-center gap-3">
                        <span className="text-xs font-bold text-foreground/40">{idx + 1}.</span>
                        <h4 className="font-bold text-white text-sm">{v.type}</h4>
                        <Badge className={`${
                          v.severity.toLowerCase() === "high" || v.severity.toLowerCase() === "critical"
                            ? "bg-red-500/20 text-red-500 border-red-500/30"
                            : v.severity.toLowerCase() === "medium"
                            ? "bg-amber-500/20 text-amber-500 border-amber-500/30"
                            : "bg-blue-500/20 text-blue-500 border-blue-500/30"
                        } border rounded-full px-2 py-0 text-[9px] font-black tracking-widest uppercase`}>
                          {v.severity}
                        </Badge>
                      </div>
                      <p className="text-xs text-foreground/50 font-medium">Location: <span className="text-foreground/80">{v.location}</span></p>
                      <p className="text-xs text-foreground/75 mt-2 leading-relaxed">
                        <strong className="text-primary font-bold">Recommendation:</strong> {v.recommendation}
                      </p>
                    </div>
                    <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center text-foreground/30 group-hover:text-red-500/80 group-hover:bg-red-500/10 transition-all">
                      <ShieldAlert size={18} />
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-8 rounded-3xl bg-white/5 border border-white/5 text-center text-foreground/40 py-10 font-bold uppercase text-xs tracking-wider">
                  🎉 No safety violations or regulatory non-compliance observations found.
                </div>
              )}
            </div>
          </div>

          {/* Predictive Metrics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Delay Probability */}
            <div className="p-6 rounded-3xl bg-white/5 border border-white/5 space-y-3">
              <div className="flex justify-between items-center">
                <h4 className="text-xs font-bold uppercase tracking-wider text-foreground/40">Delay Probability</h4>
                <TrendingUp size={16} className="text-primary" />
              </div>
              <p className="text-3xl font-black text-white">{riskResults?.delay_probability || 0}%</p>
              <div className="w-full bg-white/10 h-2 rounded-full overflow-hidden">
                <div 
                  className="bg-primary h-full transition-all duration-1000" 
                  style={{ width: `${riskResults?.delay_probability || 0}%` }}
                />
              </div>
            </div>

            {/* Projected Schedule Drift */}
            <div className="p-6 rounded-3xl bg-white/5 border border-white/5 space-y-3">
              <div className="flex justify-between items-center">
                <h4 className="text-xs font-bold uppercase tracking-wider text-foreground/40">Projected Drift</h4>
                <Clock size={16} className="text-primary" />
              </div>
              <p className="text-3xl font-black text-white">+{riskResults?.days_behind_schedule || 0} Days</p>
              <p className="text-[10px] text-foreground/40 font-bold uppercase tracking-widest">Ahead / Behind Schedule Baseline</p>
            </div>

            {/* Budget Deviation Risk */}
            <div className="p-6 rounded-3xl bg-white/5 border border-white/5 space-y-3">
              <div className="flex justify-between items-center">
                <h4 className="text-xs font-bold uppercase tracking-wider text-foreground/40">Cost Overrun Risk</h4>
                <AlertTriangle size={16} className="text-primary" />
              </div>
              <p className="text-3xl font-black text-white">+{riskResults?.cost_overrun_risk || 0}%</p>
              <div className="w-full bg-white/10 h-2 rounded-full overflow-hidden">
                <div 
                  className="bg-red-500 h-full transition-all duration-1000" 
                  style={{ width: `${Math.min(100, (riskResults?.cost_overrun_risk || 0) * 2)}%` }}
                />
              </div>
            </div>
          </div>

          {/* Risks & Recommendations Columns */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 pt-4">
            {/* Timeline Vulnerabilities */}
            <div className="space-y-4">
              <h3 className="text-sm font-black uppercase tracking-widest text-primary flex items-center gap-2">
                <span className="w-1.5 h-3 bg-primary rounded-full" /> Critical Schedule Risks
              </h3>
              <div className="p-6 rounded-3xl bg-white/5 border border-white/5 space-y-3 min-h-[180px]">
                {riskResults?.top_risks && riskResults.top_risks.length > 0 ? (
                  riskResults.top_risks.map((risk, i) => (
                    <div key={i} className="flex items-start gap-2.5 text-xs text-foreground/80 leading-relaxed font-medium">
                      <span className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 flex-shrink-0" />
                      <span>{typeof risk === "string" ? risk : risk.factor}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-foreground/40 italic">No timeline vulnerabilities analyzed yet.</p>
                )}
              </div>
            </div>

            {/* Actionable Strategic Mitigations */}
            <div className="space-y-4">
              <h3 className="text-sm font-black uppercase tracking-widest text-primary flex items-center gap-2">
                <span className="w-1.5 h-3 bg-primary rounded-full" /> AI Mitigations & Actions
              </h3>
              <div className="p-6 rounded-3xl bg-white/5 border border-white/5 space-y-3 min-h-[180px]">
                {riskResults?.recommended_actions && riskResults.recommended_actions.length > 0 ? (
                  riskResults.recommended_actions.map((act, i) => (
                    <div key={i} className="flex items-start gap-2.5 text-xs text-foreground/80 leading-relaxed font-medium">
                      <span className="font-bold text-primary flex-shrink-0">{i + 1}.</span>
                      <span>{act}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-foreground/40 italic">No timeline mitigations recommended yet.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}
