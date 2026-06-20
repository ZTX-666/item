import { motion } from "motion/react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowRight, Shield, Clock, BarChart3, Database } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background overflow-hidden relative">
      <div className="scanline" />
      
      {/* Hero Section */}
      <nav className="fixed top-0 w-full z-50 px-6 py-4 border-b border-white/5 bg-background/50 backdrop-blur-md flex justify-between items-center">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center glow-primary">
            <Shield className="text-white w-6 h-6" />
          </div>
          <span className="text-2xl font-bold tracking-tighter glow-text">SITEWATCH AI</span>
        </div>
        <div className="flex gap-8 items-center text-sm font-medium text-foreground/60">
          <Link to="#features" className="hover:text-primary transition-colors">Features</Link>
          <Link to="#ai" className="hover:text-primary transition-colors">AI Agents</Link>
          <Link to="/upload">
            <Button variant="default" className="bg-primary hover:bg-primary/90 text-white px-6">
              Launch Platform
            </Button>
          </Link>
        </div>
      </nav>

      <main className="pt-32 px-6">
        <section className="max-w-7xl mx-auto text-center relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-primary/20 bg-primary/5 text-primary text-xs font-semibold uppercase tracking-widest mb-8">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              Enterprising Construction Intelligence
            </div>
            <h1 className="text-6xl md:text-8xl font-black tracking-tighter leading-[0.9] mb-8">
              AI-POWERED <br />
              <span className="text-primary glow-text italic">CONSTRUCTION</span> <br />
              INTELLIGENCE
            </h1>
            <p className="max-w-2xl mx-auto text-lg text-foreground/60 mb-12">
              Detect safety violations, predict delays, and generate executive audit reports in seconds using AIML AI. The ultimate mission control for your build.
            </p>
            <div className="flex flex-wrap justify-center gap-6">
              <Link to="/upload">
                <Button size="lg" className="h-16 px-10 text-lg gap-3 bg-primary hover:bg-primary/90 shadow-2xl shadow-primary/20">
                  Get Started <ArrowRight className="w-5 h-5" />
                </Button>
              </Link>
              <Button size="lg" variant="outline" className="h-16 px-10 text-lg border-white/10 hover:bg-white/5">
                Watch Demo
              </Button>
            </div>
          </motion.div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-24">
            {[
              { val: "80%", label: "Delay Detection" },
              { val: "95%", label: "Safety Accuracy" },
              { val: "60s", label: "Analysis Time" },
              { val: "3", label: "AI Agents" },
            ].map((stat, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.4 + i * 0.1 }}
                className="glass-card p-8 rounded-3xl group hover:border-primary/50 transition-all"
              >
                <div className="text-4xl font-bold text-primary mb-1 group-hover:glow-text transition-all">{stat.val}</div>
                <div className="text-xs uppercase tracking-widest text-foreground/40">{stat.label}</div>
              </motion.div>
            ))}
          </div>
        </section>

        {/* Features Preview */}
        <section className="py-32 max-w-7xl mx-auto">
          <div className="grid md:grid-cols-3 gap-8">
            <FeatureCard 
              icon={<Shield className="w-8 h-8 text-primary" />}
              title="Vision Guardian"
              desc="Real-time site photo analysis detecting PPE violations, hazardous zones, and unsafe worker activities."
            />
            <FeatureCard 
              icon={<Clock className="w-8 h-8 text-primary" />}
              title="Schedule Oracle"
              desc="Analyzes project schedules to predict delay probabilities and budget deviations before they happen."
            />
            <FeatureCard 
              icon={<Database className="w-8 h-8 text-primary" />}
              title="Audit Automator"
              desc="Generates production-ready executive PDF reports with comprehensive safety and risk analytics."
            />
          </div>
        </section>
      </main>

      {/* Decorative elements */}
      <div className="absolute top-1/4 -left-64 w-[600px] h-[600px] bg-primary/10 rounded-full blur-[120px] -z-10" />
      <div className="absolute bottom-0 -right-64 w-[800px] h-[800px] bg-primary/5 rounded-full blur-[160px] -z-10" />
    </div>
  );
}

function FeatureCard({ icon, title, desc }: { icon: ReactNode, title: string, desc: string }) {
  return (
    <div className="glass-card p-10 rounded-[2.5rem] relative overflow-hidden group">
      <div className="mb-6 w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center border border-white/10 group-hover:border-primary/50 transition-all">
        {icon}
      </div>
      <h3 className="text-2xl font-bold mb-4">{title}</h3>
      <p className="text-foreground/60 leading-relaxed">{desc}</p>
      <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
        {icon}
      </div>
    </div>
  );
}
