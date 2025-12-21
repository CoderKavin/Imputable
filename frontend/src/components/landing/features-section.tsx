"use client";

import { motion, useScroll, useTransform } from "framer-motion";
import { useRef } from "react";
import { FeatureCard } from "./tilt-card";
import { History, Shield, GitMerge } from "lucide-react";

export function FeaturesSection() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start end", "end start"],
  });

  const y1 = useTransform(scrollYProgress, [0, 1], [100, -100]);
  const y2 = useTransform(scrollYProgress, [0, 1], [50, -50]);
  const y3 = useTransform(scrollYProgress, [0, 1], [150, -150]);

  const features = [
    {
      icon: <History className="w-6 h-6" />,
      title: "Immutable Versions",
      description:
        "Every change creates a new version. Nothing is ever overwritten. Time-travel to see any decision at any point in history.",
      glowColor: "cyan" as const,
      y: y1,
      delay: 0,
    },
    {
      icon: <Shield className="w-6 h-6" />,
      title: "Complete Audit Trail",
      description:
        "Know exactly who viewed, modified, or approved each decision. Export audit logs for SOC2 and compliance requirements.",
      glowColor: "purple" as const,
      y: y2,
      delay: 0.2,
    },
    {
      icon: <GitMerge className="w-6 h-6" />,
      title: "Decision Lineage",
      description:
        "Track which decisions supersede others. Understand the evolution of your architecture over time.",
      glowColor: "pink" as const,
      y: y3,
      delay: 0.4,
    },
  ];

  return (
    <section
      ref={containerRef}
      className="relative py-32 px-6 bg-black overflow-hidden"
    >
      {/* Gradient Background */}
      <div className="absolute inset-0">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />
      </div>

      <div className="relative max-w-6xl mx-auto">
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-20"
        >
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">
            Why Teams Choose{" "}
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-purple-400 to-pink-400">
              Imputable
            </span>
          </h2>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">
            Built by engineers, for engineers. Every feature solves a real pain
            point in decision documentation.
          </p>
        </motion.div>

        {/* Feature Cards with Parallax */}
        <div className="grid md:grid-cols-3 gap-8">
          {features.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 50 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{
                duration: 0.8,
                delay: feature.delay,
                type: "spring",
                stiffness: 100,
                damping: 15,
              }}
              style={{ y: feature.y }}
            >
              <FeatureCard
                icon={feature.icon}
                title={feature.title}
                description={feature.description}
                glowColor={feature.glowColor}
              />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
