import { motion } from "motion/react";
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  AreaChart, 
  Area,
  PieChart,
  Pie,
  Cell
} from "recharts";
import { 
  ShieldAlert, 
  TrendingDown, 
  Clock, 
  AlertTriangle,
  ArrowUpRight,
  Target,
  Activity
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { useProject } from "@/context/ProjectContext";
import { Link } from "react-router-dom";

const riskData = [
  { name: "Mon", risk: 24, progress: 45 },
  { name: "Tue", risk: 32, progress: 48 },
  { name: "Wed", risk: 28, progress: 52 },
  { name: "Thu", risk: 45, progress: 55 },
  { name: "Fri", risk: 38, progress: 61 },
  { name: "Sat", risk: 42, progress: 65 },
  { name: "Sun", risk: 35, progress: 68 },
];

const violationCategories = [
  { name: "PPE", value: 45, color: "#FF8C00" },
  { name: "Falling Hazards", value: 25, color: "#FF4444" },
  { name: "Electrical", value: 15, color: "#FFD700" },
  { name: "Site Entry", value: 15, color: "#3B82F6" },
];

export default function Dashboard() {
  const { visionResults, riskResults } = useProject();

  const safetyScore = visionResults?.overall_safety_score || 0;
  const violationCount = visionResults?.violations?.length || 0;
  const delayProb = riskResults?.delay_probability || 0;
  const costRisk = riskResults?.cost_overrun_risk || 0;

  if (!visionResults && !riskResults) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6 text-center">
        <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
          <Activity className="w-10 h-10 text-primary animate-pulse" />
        </div>
        <div className="space-y-2">
          <h2 className="text-3xl font-black uppercase tracking-tighter">No Active Intelligence</h2>
          <p className="text-foreground/40 max-w-sm mx-auto">Upload site documentation and photos to generate your real-time risk dashboard.</p>
        </div>
        <Link to="/upload">
          <Button size="lg" className="rounded-full px-10 bg-primary hover:bg-primary/90 text-white font-black uppercase tracking-widest">
            Initialize Upload Center
          </Button>
        </Link>
      </div>
    );
  }

  const violationCategories = [
    { name: "Total Found", value: violationCount, color: "#FF8C00" },
    { name: "Safety Grade", value: safetyScore, color: "#3B82F6" },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-8"
    >
      {/* Top Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Safety Score" 
          value={safetyScore} 
          change="+X" 
          icon={<ShieldAlert className={safetyScore > 80 ? "text-green-500" : "text-amber-500"} />} 
          type="percentage"
        />
        <StatCard 
          title="Delay Probability" 
          value={delayProb} 
          change="+X" 
          icon={<Clock className="text-red-500" />} 
          trend="up"
          type="percentage"
        />
        <StatCard 
          title="Cost Risk" 
          value={`$${costRisk}k`} 
          change="-X" 
          icon={<TrendingDown className="text-blue-500" />} 
          trend="down"
        />
        <StatCard 
          title="Active Violations" 
          value={violationCount.toString().padStart(2, '0')} 
          change="-X" 
          icon={<AlertTriangle className="text-amber-500" />} 
          trend="down"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Risk Trend Chart */}
        <Card className="lg:col-span-2 glass-card rounded-3xl border-none">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-bold uppercase tracking-widest text-foreground/40">Risk vs Progress Trend</CardTitle>
            <Badge variant="outline" className="border-primary/20 text-primary">Live Data</Badge>
          </CardHeader>
          <CardContent className="h-[350px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={riskData}>
                <defs>
                  <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#FF8C00" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#FF8C00" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                <XAxis dataKey="name" stroke="#666" fontSize={10} tickLine={false} axisLine={false} />
                <YAxis stroke="#666" fontSize={10} tickLine={false} axisLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: "#151515", border: "1px solid #333", borderRadius: "12px" }}
                  labelStyle={{ color: "#FF8C00", fontWeight: "bold" }}
                />
                <Area type="monotone" dataKey="risk" stroke="#FF8C00" fillOpacity={1} fill="url(#colorRisk)" strokeWidth={3} />
                <Area type="monotone" dataKey="progress" stroke="#3B82F6" fillOpacity={0} strokeWidth={2} strokeDasharray="5 5" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Violation Categories */}
        <Card className="glass-card rounded-3xl border-none">
          <CardHeader>
            <CardTitle className="text-sm font-bold uppercase tracking-widest text-foreground/40">AI Analysis Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px] w-full relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={violationCategories}
                    innerRadius={70}
                    outerRadius={90}
                    paddingAngle={8}
                    dataKey="value"
                  >
                    {violationCategories.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-3xl font-black">{violationCount}</span>
                <span className="text-[10px] uppercase tracking-widest text-foreground/40">Total Events</span>
              </div>
            </div>
            <div className="mt-8 space-y-3">
              {visionResults?.violations?.slice(0, 3)?.map((v, i) => (
                <div key={i} className="flex items-center justify-between p-2 rounded-xl bg-white/5 border border-white/5">
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={12} className="text-amber-500" />
                    <span className="text-[10px] font-medium truncate max-w-[150px]">{v.type}</span>
                  </div>
                  <Badge variant="outline" className="text-[8px] border-amber-500/20 text-amber-500">{v.severity}</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Project Target Card */}
        <Card className="glass-card rounded-3xl border-none overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-10">
            <Target size={120} className="text-primary" />
          </div>
          <CardHeader>
            <CardTitle className="text-sm font-bold uppercase tracking-widest text-foreground/40">Project Velocity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div>
              <div className="flex justify-between mb-4">
                <span className="text-2xl font-black">{visionResults?.progress_estimate || 0}%</span>
                <Badge className="bg-primary/20 text-primary border-none">Visual Estimation</Badge>
              </div>
              <Progress value={visionResults?.progress_estimate || 0} className="h-4 bg-white/5 rounded-full" />
            </div>
            <div className="grid grid-cols-2 gap-8 pt-4 text-left">
              <div className="flex flex-col">
                <span className="text-xs text-foreground/40 uppercase tracking-widest mb-1">Target End Date</span>
                <span className="text-lg font-bold">{riskResults?.target_end_date || "Oct 24, 2026"}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-foreground/40 uppercase tracking-widest mb-1">Risk Status</span>
                <span className={cn("text-lg font-bold", 
                  (riskResults?.risk_status?.toLowerCase()?.includes("delay") || riskResults?.risk_status?.toLowerCase()?.includes("risk") || delayProb > 50) 
                    ? "text-red-500" 
                    : "text-green-500"
                )}>
                  {riskResults?.risk_status || (delayProb > 50 ? "Critical Delay" : "On Track")}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* AI Insight Card */}
        <Card className="glass-card rounded-3xl border-none bg-gradient-to-br from-primary/10 to-transparent relative overflow-hidden group">
          <CardHeader>
            <CardTitle className="text-sm font-bold uppercase tracking-widest text-primary flex items-center gap-2">
              <Activity size={16} /> AI Executive Summary
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg leading-relaxed text-foreground/80 mb-6">
              "{visionResults?.summary || "No visual summary available yet."}"
            </p>
            <div className="flex gap-4">
              <Link to="/reports">
                <Button size="sm" className="bg-primary text-white rounded-full px-6">View Findings</Button>
              </Link>
            </div>
          </CardContent>
          <div className="absolute -right-20 -bottom-20 w-64 h-64 bg-primary/20 rounded-full blur-[100px]" />
        </Card>
      </div>
    </motion.div>
  );
}

function StatCard({ title, value, change, icon, trend = "up", type = "value" }: any) {
  return (
    <Card className="glass-card rounded-3xl border-none hover:translate-y-[-4px] transition-all cursor-pointer group">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-[10px] font-bold uppercase tracking-[0.2em] text-foreground/40">{title}</CardTitle>
        <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center border border-white/10 group-hover:border-primary/50 transition-colors">
          {icon}
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline gap-2">
          <span className="text-4xl font-black tracking-tighter">{value}{type === "percentage" ? "%" : ""}</span>
          <div className={cn(
            "flex items-center text-[10px] font-bold",
            trend === "up" ? "text-green-500" : "text-red-500"
          )}>
            <ArrowUpRight size={10} className={cn(trend === "down" && "rotate-90")} />
            {change}%
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function cn(...inputs: any[]) {
  return inputs.filter(Boolean).join(" ");
}
