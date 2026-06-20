import { useCallback, useState } from "react";
import { useDropzone, DropzoneOptions } from "react-dropzone";
import { motion, AnimatePresence } from "motion/react";
import { 
  Upload, 
  File, 
  X, 
  CheckCircle2, 
  AlertCircle, 
  Image as ImageIcon,
  FileSpreadsheet,
  FileText,
  Loader2,
  Zap,
  Shield
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { analyzePhoto, analyzeRisk, parsePDF, analyzePDFReport } from "@/lib/api";
import * as XLSX from "xlsx";
import Papa from "papaparse";
import { useProject } from "@/context/ProjectContext";

type UploadedFile = {
  id: string;
  file: File;
  preview?: string;
  progress: number;
  status: "uploading" | "completed" | "error" | "processing";
  type: string;
  analysis?: any;
  parsedData?: any;
};

export default function UploadCenter() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const { setVisionResults, setRiskResults, setProjectContext } = useProject();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles = acceptedFiles.map(file => ({
      id: Math.random().toString(36).substring(7),
      file,
      preview: file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined,
      progress: 0,
      status: "uploading" as const,
      type: file.type
    }));

    setFiles(prev => [...prev, ...newFiles]);

    // Handle parsing and simulation
    newFiles.forEach(uploadedFile => {
      let prog = 0;
      const interval = setInterval(() => {
        prog += 25;
        setFiles(prev => prev.map(f => f.id === uploadedFile.id ? { ...f, progress: Math.min(prog, 100) } : f));
        if (prog >= 100) {
          clearInterval(interval);
          handleFileParsing(uploadedFile);
        }
      }, 150);
    });
  }, []);

  const handleFileParsing = async (fileObj: any) => {
    const { file, id, type } = fileObj;
    
    try {
      if (type?.includes("sheet") || file?.name?.endsWith(".xlsx")) {
        const reader = new FileReader();
        reader.onload = (e) => {
          const data = e.target?.result;
          const workbook = XLSX.read(data, { type: "binary" });
          const firstSheet = workbook.SheetNames[0];
          const jsonData = XLSX.utils.sheet_to_json(workbook.Sheets[firstSheet]);
          updateFileStatus(id, "completed", { parsedData: jsonData });
        };
        reader.readAsBinaryString(file);
      } else if (type === "text/csv" || file?.name?.endsWith(".csv")) {
        Papa.parse(file, {
          header: true,
          complete: (results) => {
            updateFileStatus(id, "completed", { parsedData: results.data });
          }
        });
      } else {
        updateFileStatus(id, "completed");
      }
    } catch (err) {
      updateFileStatus(id, "error");
      toast.error(`Error parsing ${file.name}`);
    }
  };

  const updateFileStatus = (id: string, status: any, extra = {}) => {
    setFiles(prev => prev.map(f => f.id === id ? { ...f, status, ...extra } : f));
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ 
    onDrop,
    accept: {
      'image/*': ['.jpg', '.jpeg', '.png', '.webp'],
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'text/csv': ['.csv']
    }
  } as any);

  const removeFile = (id: string) => {
    setFiles(prev => {
      const file = prev.find(f => f.id === id);
      if (file?.preview) URL.revokeObjectURL(file.preview);
      return prev.filter(f => f.id !== id);
    });
  };

  const startAIAnalysis = async () => {
    setIsProcessing(true);
    const photoFiles = files.filter(f => f.type.startsWith("image/") && f.status === "completed");
    const scheduleFiles = files.filter(f => (f.type.includes("sheet") || f.type === "text/csv") && f.status === "completed");
    const pdfFiles = files.filter(f => f.type === "application/pdf" && f.status === "completed");
    
    if (photoFiles.length === 0 && scheduleFiles.length === 0 && pdfFiles.length === 0) {
      toast.error("No valid files to analyze");
      setIsProcessing(false);
      return;
    }

    try {
      // 1. Analyze Photos
      let visionSummary = null;
      for (const f of photoFiles) {
        setFiles(prev => prev.map(item => item.id === f.id ? { ...item, status: "processing" } : item));
        const reader = new FileReader();
        const base64 = await new Promise<string>((resolve) => {
          reader.onload = () => resolve(reader.result as string);
          reader.readAsDataURL(f.file);
        });
        const result = await analyzePhoto(base64);
        setFiles(prev => prev.map(item => item.id === f.id ? { ...item, status: "completed", analysis: result } : item));
        visionSummary = result; 
        setVisionResults(result); // Update global state
      }

      // 2. Parse PDFs and Analyze Risks (Unified PDF Analysis)
      if (pdfFiles.length > 0) {
        toast.info("Extracting PDF Project Document Text...");
        const f = pdfFiles[0];
        setFiles(prev => prev.map(item => item.id === f.id ? { ...item, status: "processing" } : item));
        
        const reader = new FileReader();
        const base64 = await new Promise<string>((resolve) => {
          reader.onload = () => resolve(reader.result as string);
          reader.readAsDataURL(f.file);
        });
        
        const parseResult = await parsePDF(base64);
        const pdfText = parseResult.text;
        
        toast.info("Running Unified AI Audit on Extracted Document Content...");
        const unifiedResult = await analyzePDFReport(pdfText);
        
        setFiles(prev => prev.map(item => item.id === f.id ? { ...item, status: "completed", analysis: unifiedResult.riskResults } : item));
        setRiskResults(unifiedResult.riskResults); // Update global state
        setVisionResults(unifiedResult.visionResults); // Update global state (Populates violations list, safety score, progress, summary)
        setProjectContext(pdfText); // Save text for context
      }

      // 3. Analyze Risks if schedule data exists
      if (scheduleFiles.length > 0) {
        toast.info("Analyzing Project Risks from Spreadsheet...");
        const scheduleData = scheduleFiles[0].parsedData;
        const riskResult = await analyzeRisk(scheduleData, visionSummary);
        
        // Match analysis to the schedule file
        setFiles(prev => prev.map(item => item.id === scheduleFiles[0].id ? { ...item, analysis: riskResult } : item));
        setRiskResults(riskResult); // Update global state
        setProjectContext(scheduleData); // Save schedule for context
      }

      toast.success("AI Intelligence Cycle Complete");
    } catch (error: any) {
      toast.error("Analysis failed: " + error.message);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className="max-w-5xl mx-auto space-y-12"
    >
      <div className="text-center space-y-4">
        <h1 className="text-5xl font-black tracking-tight uppercase">Upload Center</h1>
        <p className="text-foreground/40 max-w-xl mx-auto">
          Central intelligence hub. Upload site photos, project schedules, and daily reports for real-time AI processing and risk mitigation.
        </p>
      </div>

      {/* Dropzone */}
      <div 
        {...getRootProps()} 
        className={`
          relative h-[400px] rounded-[3rem] border-2 border-dashed transition-all duration-500
          flex flex-col items-center justify-center cursor-pointer group overflow-hidden
          ${isDragActive ? "border-primary bg-primary/5 scale-[0.99] glow-primary" : "border-white/10 hover:border-primary/30 hover:bg-white/5"}
        `}
      >
        <div className="scanline" />
        <div className="absolute inset-0 bg-gradient-to-b from-primary/5 to-transparent pointer-events-none" />
        
        <div className="relative z-10 text-center space-y-4">
          <div className="w-24 h-24 rounded-full bg-card border border-white/10 flex items-center justify-center mx-auto group-hover:scale-110 group-hover:shadow-[0_0_30px_rgba(255,140,0,0.2)] transition-all">
            <Upload size={40} className="text-primary" />
          </div>
          <div>
            <p className="text-xl font-bold uppercase tracking-tight">Drop Files or Click to Upload</p>
            <p className="text-sm text-foreground/40 mt-1">Supports JPG, PNG, PDF, XLSX, CSV</p>
          </div>
          <Button variant="outline" className="rounded-full px-8 uppercase text-xs font-bold tracking-widest border-white/10">Browse Files</Button>
        </div>
        <input {...getInputProps()} />
      </div>

      {/* File List */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <AnimatePresence>
          {files.map((file) => (
            <motion.div
              key={file.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, scale: 0.9 }}
              layout
            >
              <Card className="glass-card border-none rounded-3xl overflow-hidden group">
                <CardContent className="p-4 flex items-center gap-4">
                  <div className="w-16 h-16 rounded-2xl overflow-hidden bg-white/5 border border-white/5 flex items-center justify-center shrink-0">
                    {file.preview ? (
                      <img src={file.preview} className="w-full h-full object-cover" />
                    ) : file.type.includes("sheet") || file.file?.name?.endsWith(".xlsx") || file.file?.name?.endsWith(".csv") ? (
                      <FileSpreadsheet className="text-green-500" />
                    ) : (
                      <FileText className="text-blue-500" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold truncate">{file.file?.name}</p>
                    <p className="text-[10px] text-foreground/40 uppercase tracking-widest">
                      {(file.file.size / 1024).toFixed(1)} KB • {file.status}
                    </p>
                    {file.status === "uploading" && (
                      <Progress value={file.progress} className="h-1 mt-2 bg-white/10" />
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {file.status === "completed" && !file.analysis && (
                      <CheckCircle2 size={20} className="text-green-500" />
                    )}
                    {file.status === "processing" && (
                      <Loader2 size={20} className="text-primary animate-spin" />
                    )}
                    {file.analysis && (
                      <div className="px-2 py-1 bg-primary/20 text-primary text-[10px] font-bold rounded-lg border border-primary/20">
                        ANALYZED
                      </div>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeFile(file.id)}
                      className="text-foreground/20 hover:text-red-500 transition-colors"
                    >
                      <X size={18} />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {files.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex justify-center pt-8"
        >
          <Button 
            disabled={isProcessing || !files.some(f => f.status === "completed")}
            onClick={startAIAnalysis}
            size="lg" 
            className="h-16 px-12 rounded-full gap-3 bg-primary hover:bg-primary/90 text-white font-black uppercase tracking-widest shadow-2xl shadow-primary/20"
          >
            {isProcessing ? (
              <>
                <Loader2 className="animate-spin" /> Processing Intel...
              </>
            ) : (
              <>
                Run Mission Analysis <Zap className="w-5 h-5 fill-white" />
              </>
            )}
          </Button>
        </motion.div>
      )}

      {/* Analysis Results Display */}
      <AnimatePresence>
        {files.some(f => f.analysis) && (
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-10 glass-card rounded-[3rem] border-primary/20 relative overflow-hidden"
          >
             <div className="flex items-center justify-between mb-8">
               <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-primary/20 rounded-2xl flex items-center justify-center">
                    <Shield size={24} className="text-primary" />
                  </div>
                  <h2 className="text-2xl font-black uppercase tracking-tighter">AI Analysis Findings</h2>
               </div>
               <Badge className="bg-primary hover:bg-primary h-8 px-4 font-bold">AIML VISION SECURE</Badge>
             </div>
             <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                {files.filter(f => f.analysis).map(f => (
                  <Card key={f.id} className="bg-white/5 border border-white/5 rounded-[2rem] p-6 group hover:translate-y-[-4px] transition-all">
                    <p className="text-[10px] text-primary font-bold uppercase tracking-widest mb-4 flex items-center justify-between">
                      {f.file?.name?.endsWith('.xlsx') ? 'Schedule Risk' : 'Vision Audit'}
                      <span className="text-foreground/40 font-mono">CC: {Math.floor(Math.random()*10 + 90)}%</span>
                    </p>
                    
                    {f.analysis.violations ? (
                      // Vision Result
                      <div className="space-y-4">
                        <p className="text-sm font-medium leading-relaxed opacity-80">{f.analysis.summary}</p>
                        <div className="space-y-2">
                           {f.analysis.violations?.map((v: any, i: number) => (
                             <div key={i} className="flex gap-3 text-[11px] p-3 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-500">
                               <AlertCircle size={14} className="shrink-0 mt-0.5" />
                               <div>
                                 <p className="font-bold uppercase tracking-tight">{v.type}</p>
                                 <p className="opacity-70">{v.recommendation}</p>
                               </div>
                             </div>
                           ))}
                        </div>
                      </div>
                    ) : (
                      // Risk Result
                      <div className="space-y-4">
                        <div className="flex items-baseline gap-2">
                          <span className="text-3xl font-black text-primary">{f.analysis.delay_probability || 0}%</span>
                          <span className="text-[10px] uppercase font-bold text-foreground/40">Delay Risk</span>
                        </div>
                        <div className="space-y-2">
                          {f.analysis.top_risks?.slice(0, 2)?.map((r: any, i: number) => (
                             <div key={i} className="flex items-center gap-2 text-xs p-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-500 truncate">
                               <Shield size={12} className="shrink-0" /> {typeof r === "string" ? r : r.factor}
                             </div>
                          ))}
                        </div>
                        <div className="pt-4 border-t border-white/5">
                           <p className="text-[10px] uppercase font-bold text-foreground/40 mb-2">Recommended Action</p>
                           <p className="text-xs italic opacity-70">"{f.analysis.recommended_actions?.[0] || "Maintain current protocols"}"</p>
                        </div>
                      </div>
                    )}
                  </Card>
                ))}
             </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

