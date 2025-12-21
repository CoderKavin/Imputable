"use client";

import { motion } from "framer-motion";
import { useState } from "react";
import { Shield, Zap, FileCheck, Clock, Users, GitBranch } from "lucide-react";

interface BentoCardProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  className?: string;
  delay?: number;
}

function BentoCard({
  title,
  description,
  icon,
  className = "",
  delay = 0,
}: BentoCardProps) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-100px" }}
      transition={{
        duration: 0.6,
        delay,
        type: "spring",
        stiffness: 100,
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`relative group ${className}`}
    >
      {/* Gradient border glow effect */}
      <div
        className="absolute -inset-[1px] rounded-2xl transition-opacity duration-500"
        style={{
          opacity: isHovered ? 1 : 0,
          background:
            "linear-gradient(135deg, #06b6d4, #8b5cf6, #ec4899, #06b6d4)",
          backgroundSize: "300% 300%",
          animation: isHovered ? "gradient-shift 3s ease infinite" : "none",
        }}
      />

      {/* Static subtle border (always visible) */}
      <div
        className="absolute -inset-[1px] rounded-2xl transition-opacity duration-500"
        style={{
          opacity: isHovered ? 0 : 1,
          background:
            "linear-gradient(135deg, rgba(255,255,255,0.1), rgba(255,255,255,0.05))",
        }}
      />

      {/* Inner Card */}
      <div className="relative h-full rounded-2xl bg-black/90 backdrop-blur-xl p-6">
        {/* Shimmer effect on hover */}
        <div
          className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none"
          style={{ opacity: isHovered ? 1 : 0 }}
        >
          <div
            className="absolute w-32 h-[200%] bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-y-1/4 -rotate-12"
            style={{
              animation: isHovered ? "shimmer 2s ease-in-out infinite" : "none",
            }}
          />
        </div>

        {/* Content */}
        <div className="relative z-10">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500/20 to-purple-500/20 border border-white/10 flex items-center justify-center mb-4 group-hover:scale-110 group-hover:border-cyan-500/30 transition-all duration-300">
            <div className="text-cyan-400">{icon}</div>
          </div>
          <h3 className="text-xl font-semibold text-white mb-2">{title}</h3>
          <p className="text-gray-400 text-sm leading-relaxed">{description}</p>
        </div>
      </div>
    </motion.div>
  );
}

export function BentoGrid() {
  return (
    <section className="relative py-32 px-6 bg-black overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-purple-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative max-w-6xl mx-auto">
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">
            Built for{" "}
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-purple-400">
              Enterprise Teams
            </span>
          </h2>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">
            Every feature designed to help you make better decisions, faster.
          </p>
        </motion.div>

        {/* Bento Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <BentoCard
            title="Immutable History"
            description="Every change creates a new version. Time-travel through your decision history. Nothing is ever overwritten or lost."
            icon={<GitBranch className="w-6 h-6" />}
            className="md:col-span-2 lg:col-span-1"
            delay={0}
          />

          <BentoCard
            title="SOC2 Compliant"
            description="Export audit trails for compliance. Cryptographic verification ensures tamper-proof records."
            icon={<Shield className="w-6 h-6" />}
            delay={0.1}
          />

          <BentoCard
            title="Lightning Fast"
            description="Sub-100ms response times. Built on modern infrastructure that scales with your team."
            icon={<Zap className="w-6 h-6" />}
            delay={0.2}
          />

          <BentoCard
            title="Approval Workflows"
            description="Route decisions to the right people. Track who approved what and when."
            icon={<FileCheck className="w-6 h-6" />}
            delay={0.3}
          />

          <BentoCard
            title="Tech Debt Timer"
            description="Set review dates on temporary decisions. Get alerts before tech debt becomes a crisis."
            icon={<Clock className="w-6 h-6" />}
            delay={0.4}
          />

          <BentoCard
            title="Team Collaboration"
            description="Multi-tenant organizations. Role-based access. Your decisions, your team, your rules."
            icon={<Users className="w-6 h-6" />}
            delay={0.5}
          />
        </div>
      </div>

      {/* CSS for animations */}
      <style jsx>{`
        @keyframes shimmer {
          0% {
            transform: translateX(-200%) translateY(-25%) rotate(-12deg);
          }
          100% {
            transform: translateX(200%) translateY(-25%) rotate(-12deg);
          }
        }
        @keyframes gradient-shift {
          0% {
            background-position: 0% 50%;
          }
          50% {
            background-position: 100% 50%;
          }
          100% {
            background-position: 0% 50%;
          }
        }
      `}</style>
    </section>
  );
}
