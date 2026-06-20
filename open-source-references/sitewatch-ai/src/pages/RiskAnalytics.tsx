import { motion } from "motion/react";
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  LineChart,
  Line
} from "recharts";
import { 
  TrendingUp, 
  AlertCircle, 
  Calendar,
  DollarSign,
  Zap
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useProject } from "@/context/ProjectContext";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Activity } from "lucide-react";

const riskTimeline = [
  { day: 1, probability: 10, cost: 0 },
  { day: 5, probability: 15, cost: 2000 },
  { day: 10, probability: 45, cost: 8000 },
  { day: 15, probability: 35, cost: 15000 },
  { day: 20, probability: 60, cost: 35000 },
  { day: 25, probability: 55, cost: 42000 },
  { day: 30, probability: 75, cost: 68000 },
];

export default function RiskAnalytics() {
  const { riskResults } = useProject();

  if (!riskResults) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6 text-center">
        <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
          <Activity className="w-10 h-10 text-primary animate-pulse" />
        </div>
        <div className="space-y-2">
          <h2 className="text-3xl font-black uppercase tracking-tighter">Mission Data Missing</h2>
          <p className="text-foreground/40 max-w-sm mx-auto">Upload project schedules to run AIML's predictive risk models.</p>
        </div>
        <Link to="/upload">
          <Button size="lg" className="rounded-full px-10 bg-primary hover:bg-primary/90 text-white font-black uppercase tracking-widest">
            Go to Upload Center
          </Button>
        </Link>
      </div>
    );
  }

  const riskTimeline = [
    { day: "Current", probability: riskResults.delay_probability, cost: riskResults.cost_overrun_risk },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-8"
    >
      <div className="flex justify-between items-end">
        <div className="space-y-1">
          <h1 className="text-4xl font-black uppercase tracking-tighter">Risk Predictor</h1>
          <p className="text-foreground/40 font-medium">AIML-powered delay & cost forecasting</p>
        </div>
        <Badge className="bg-primary/20 text-primary border-primary/20 h-8 px-4 font-bold">
          Model: SiteWise-Risk-v2
        </Badge>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Core Prediction Matrix */}
        <Card className="lg:col-span-2 glass-card border-none rounded-[2.5rem] bg-gradient-to-br from-primary/5 to-transparent">
          <CardHeader>
            <CardTitle className="text-sm font-bold uppercase tracking-widest text-foreground/40">Risk Probability Matrix</CardTitle>
          </CardHeader>
          <CardContent className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={riskTimeline}>
                 <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                 <XAxis dataKey="day" stroke="#666" fontSize={10} />
                 <YAxis stroke="#666" fontSize={10} />
                 <Tooltip 
                   contentStyle={{ backgroundColor: "#151515", border: "1px solid #333", borderRadius: "12px" }}
                   itemStyle={{ fontWeight: "bold" }}
                 />
                 <Bar dataKey="probability" name="Delay Prob (%)" fill="#FF8C00" radius={[10, 10, 0, 0]} />
                 <Bar dataKey="cost" name="Cost Risk ($k)" fill="#3B82F6" radius={[10, 10, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Prediction Insights */}
        <div className="space-y-6">
          <InsightCard 
            icon={<TrendingUp className="text-primary" />}
            title="Delay Probability"
            value={`${riskResults.delay_probability}%`}
            desc={`AIML estimates a ${riskResults.delay_probability}% chance of timeline deviation.`}
          />
          <InsightCard 
            icon={<DollarSign className="text-green-500" />}
            title="Projected Overrun"
            value={`$${riskResults.cost_overrun_risk}k`}
            desc="Estimated budget deviation based on current schedule bottlenecks."
          />
          <InsightCard 
            icon={<Calendar className="text-blue-500" />}
            title="Drift Index"
            value={`+${riskResults.days_behind_schedule} Days`}
            desc="Cumulative drift identified in the provided project schedule."
          />
        </div>
      </div>

      {/* Critical Risks Table */}
      <Card className="glass-card border-none rounded-[2.5rem]">
        <CardHeader>
          <CardTitle className="text-sm font-bold uppercase tracking-widest text-foreground/40">Critical Risk Matrix</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {riskResults.top_risks?.map((risk, i) => {
              const severity = typeof risk === "string" ? (i === 0 ? "HIGH" : "MEDIUM") : risk.severity;
              const factor = typeof risk === "string" ? risk : risk.factor;
              const prob = typeof risk === "string" ? `${riskResults.delay_probability}%` : `${risk.probability}%`;
              return (
                <RiskRow 
                  key={i} 
                  severity={severity} 
                  factor={factor} 
                  impact="Direct" 
                  prob={prob} 
                />
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Actionable Recommendations */}
      <div className="p-10 rounded-[3rem] bg-primary text-white relative overflow-hidden group">
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 bg-white/20 backdrop-blur-md rounded-2xl flex items-center justify-center">
              <Zap className="fill-white" />
            </div>
            <h2 className="text-2xl font-black uppercase tracking-tight italic">AI Mitigation Engines</h2>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {riskResults.recommended_actions?.map((action, i) => (
              <div key={i} className="space-y-2">
                <h4 className="font-bold border-b border-white/20 pb-2">Strategem #{i+1}</h4>
                <p className="text-sm text-white/70">{action}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="absolute top-0 right-0 p-12 opacity-10 rotate-12 group-hover:scale-110 transition-transform">
           <Zap size={200} fill="white" />
        </div>
      </div>
    </motion.div>
  );
}

function InsightCard({ icon, title, value, desc }: any) {
  return (
    <Card className="glass-card border-none rounded-3xl p-6 relative overflow-hidden group hover:border-primary/20 transition-all">
       <div className="flex items-center gap-4 mb-4">
          <div className="p-3 bg-white/5 rounded-2xl border border-white/10 group-hover:border-primary/50 transition-colors">
            {icon}
          </div>
          <div>
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-foreground/40">{title}</h4>
            <div className="text-2xl font-black text-primary">{value}</div>
          </div>
       </div>
       <p className="text-xs text-foreground/60 leading-relaxed">{desc}</p>
    </Card>
  );
}

function RiskRow({ severity, factor, impact, prob }: any) {
  const color = severity === "HIGH" ? "text-red-500" : severity === "MEDIUM" ? "text-amber-500" : "text-green-500";
  return (
    <div className="flex items-center justify-between p-4 rounded-2xl bg-white/5 border border-white/5 hover:bg-white/10 transition-all">
      <div className="flex items-center gap-4 lg:gap-12">
        <Badge variant="outline" className={cn("border-none px-3 font-black text-[10px]", 
          severity === "HIGH" ? "bg-red-500/10 text-red-500" : 
          severity === "MEDIUM" ? "bg-amber-500/10 text-amber-500" : 
          "bg-green-500/10 text-green-500")}>
          {severity}
        </Badge>
        <span className="font-bold text-sm min-w-[200px]">{factor}</span>
      </div>
      <div className="flex items-center gap-12">
        <span className="text-xs font-medium text-foreground/40 uppercase tracking-widest">{impact}</span>
        <span className="text-lg font-black text-primary">{prob}</span>
      </div>
    </div>
  );
}

function cn(...inputs: any[]) {
  return inputs.filter(Boolean).join(" ");
}
