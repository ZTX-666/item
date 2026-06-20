import { useState } from "react";
import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import { 
  LayoutDashboard, 
  Upload, 
  BarChart2, 
  FileText, 
  ChevronRight, 
  Shield, 
  Zap,
  Menu,
  X
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const navItems = [
  { name: "Dashboard", icon: LayoutDashboard, path: "/dashboard" },
  { name: "Upload Center", icon: Upload, path: "/upload" },
  { name: "Risk Analytics", icon: BarChart2, path: "/risk" },
  { name: "Reports", icon: FileText, path: "/reports" },
];

export default function Layout({ children }: { children: ReactNode }) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const location = useLocation();

  return (
    <div className="flex min-h-screen bg-background text-foreground font-sans text-left">
      <div className="scanline opacity-20" />
      
      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{ width: isSidebarOpen ? 280 : 80 }}
        className={cn(
          "fixed left-0 top-0 h-full bg-card/30 backdrop-blur-xl border-r border-white/5 z-40 transition-all duration-300",
          !isSidebarOpen && "items-center"
        )}
      >
        <div className="p-6 flex items-center justify-between">
          <AnimatePresence mode="wait">
            {isSidebarOpen ? (
              <motion.div
                key="logo-full"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-2"
              >
                <div className="w-8 h-8 bg-primary rounded shadow-[0_0_15px_rgba(255,140,0,0.5)] flex items-center justify-center">
                  <Shield className="w-5 h-5 text-white" />
                </div>
                <span className="font-black tracking-tighter text-xl">SITEWATCH</span>
              </motion.div>
            ) : (
              <motion.div
                key="logo-small"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="w-10 h-10 bg-primary rounded shadow-[0_0_15px_rgba(255,140,0,0.5)] flex items-center justify-center mx-auto"
              >
                <Shield className="w-6 h-6 text-white" />
              </motion.div>
            )}
          </AnimatePresence>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="hover:bg-white/5 text-foreground/40"
          >
            {isSidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </Button>
        </div>

        <nav className="mt-8 px-4 space-y-2">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link key={item.name} to={item.path}>
                <div
                  className={cn(
                    "flex items-center gap-4 px-4 py-3 rounded-xl transition-all duration-200 group relative",
                    isActive 
                      ? "bg-primary/10 text-primary border border-primary/20 shadow-[0_0_20px_rgba(255,140,0,0.05)]" 
                      : "text-foreground/40 hover:bg-white/5 hover:text-foreground"
                  )}
                >
                  <item.icon size={22} className={cn(isActive && "glow-primary")} />
                  {isSidebarOpen && (
                    <span className="font-semibold text-sm">{item.name}</span>
                  )}
                  {isActive && (
                    <motion.div
                      layoutId="sidebar-indicator"
                      className="absolute left-0 w-1 h-6 bg-primary rounded-r-full"
                    />
                  )}
                </div>
              </Link>
            );
          })}
        </nav>

        {isSidebarOpen && (
          <div className="absolute bottom-10 left-6 right-6">
            <div className="p-6 rounded-2xl bg-gradient-to-br from-primary/20 to-transparent border border-primary/10 relative overflow-hidden group">
              <Zap className="w-8 h-8 text-primary mb-4 animate-pulse" />
              <h4 className="font-bold text-sm mb-1 uppercase tracking-wider">AI ENGINE PRO</h4>
              <p className="text-[10px] text-foreground/40 leading-tight">Advanced site monitoring active. AIML Vision connected.</p>
              <div className="absolute -right-4 -bottom-4 w-16 h-16 bg-primary/20 rounded-full blur-2xl group-hover:scale-150 transition-transform" />
            </div>
          </div>
        )}
      </motion.aside>

      <main 
        className={cn(
          "flex-1 transition-all duration-300 min-h-screen",
          isSidebarOpen ? "pl-[280px]" : "pl-[80px]"
        )}
      >
        <header className="h-20 border-b border-white/5 px-8 flex items-center justify-between sticky top-0 bg-background/50 backdrop-blur-md z-30">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-bold tracking-tight uppercase text-foreground/40">
              {navItems.find(n => n.path === location.pathname)?.name || "Dashboard"}
            </h2>
            <ChevronRight size={16} className="text-foreground/20" />
            <span className="text-sm font-medium text-foreground/80">Project: Neo-Industrial Complex</span>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-xs font-mono text-green-500/80 tracking-widest">LIVE SYSTEM OK</span>
            </div>
            <div className="w-10 h-10 rounded-full bg-card border border-white/10 flex items-center justify-center font-bold text-sm text-primary">
              JS
            </div>
          </div>
        </header>
        
        <div className="p-8 pb-20">
          {children}
        </div>
      </main>
    </div>
  );
}
