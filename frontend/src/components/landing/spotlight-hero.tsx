"use client";

import { useRef, useState, useEffect } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight, Sparkles } from "lucide-react";

export function SpotlightHero() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);

  // Mouse position
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  // Smooth spring animation for spotlight
  const spotlightX = useSpring(mouseX, { stiffness: 200, damping: 30 });
  const spotlightY = useSpring(mouseY, { stiffness: 200, damping: 30 });

  // Spotlight size based on hover
  const spotlightSize = useSpring(isHovered ? 400 : 300, {
    stiffness: 200,
    damping: 30,
  });

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    mouseX.set(e.clientX - rect.left);
    mouseY.set(e.clientY - rect.top);
  };

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="relative min-h-screen overflow-hidden bg-black"
    >
      {/* Dot Grid Background */}
      <div
        className="absolute inset-0 opacity-20"
        style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, rgba(255,255,255,0.3) 1px, transparent 0)`,
          backgroundSize: "40px 40px",
        }}
      />

      {/* Radial Fade Mask */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 0%, black 70%)",
        }}
      />

      {/* Spotlight Effect */}
      <motion.div
        className="absolute pointer-events-none"
        style={{
          x: spotlightX,
          y: spotlightY,
          width: spotlightSize,
          height: spotlightSize,
          translateX: "-50%",
          translateY: "-50%",
          background:
            "radial-gradient(circle, rgba(6,182,212,0.15) 0%, rgba(139,92,246,0.1) 30%, transparent 70%)",
          filter: "blur(40px)",
        }}
      />

      {/* Secondary Glow */}
      <motion.div
        className="absolute pointer-events-none"
        style={{
          x: spotlightX,
          y: spotlightY,
          width: useTransform(spotlightSize, (s) => s * 0.5),
          height: useTransform(spotlightSize, (s) => s * 0.5),
          translateX: "-50%",
          translateY: "-50%",
          background:
            "radial-gradient(circle, rgba(6,182,212,0.3) 0%, transparent 60%)",
          filter: "blur(20px)",
        }}
      />

      {/* Ambient Glow Orbs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl animate-pulse" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse delay-1000" />

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen px-6">
        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-8"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 bg-white/5 backdrop-blur-sm">
            <Sparkles className="w-4 h-4 text-cyan-400" />
            <span className="text-sm text-gray-300">
              Trusted by 500+ engineering teams
            </span>
          </div>
        </motion.div>

        {/* Main Heading with Animated Gradient */}
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="text-5xl md:text-7xl lg:text-8xl font-bold text-center max-w-5xl mb-6"
        >
          <span className="text-white">Never Forget </span>
          <span className="relative inline-block">
            <span
              className="bg-clip-text text-transparent animate-gradient-x"
              style={{
                backgroundImage:
                  "linear-gradient(90deg, #06b6d4, #8b5cf6, #ec4899, #06b6d4)",
                backgroundSize: "300% 100%",
              }}
            >
              Why
            </span>
          </span>
          <br />
          <span className="text-white">You Built It</span>
        </motion.h1>

        {/* Subheading */}
        <motion.p
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="text-lg md:text-xl text-gray-400 text-center max-w-2xl mb-12"
        >
          The immutable decision ledger for engineering teams. Track every
          choice, preserve full context, and build institutional memory that
          survives team changes.
        </motion.p>

        {/* CTA Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.6 }}
          className="flex flex-col sm:flex-row items-center gap-4"
        >
          <Link href="/sign-up">
            <Button
              size="lg"
              className="relative group px-8 py-6 text-lg bg-gradient-to-r from-cyan-500 to-purple-600 hover:from-cyan-400 hover:to-purple-500 border-0 rounded-xl"
            >
              <span className="relative z-10 flex items-center gap-2">
                Start Free Trial
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </span>
              {/* Glow effect */}
              <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-cyan-500 to-purple-600 blur-xl opacity-50 group-hover:opacity-75 transition-opacity" />
            </Button>
          </Link>
          <Link href="/sign-in">
            <Button
              variant="outline"
              size="lg"
              className="px-8 py-6 text-lg border-white/20 bg-white/5 hover:bg-white/10 text-white rounded-xl backdrop-blur-sm"
            >
              Sign In
            </Button>
          </Link>
        </motion.div>

        {/* Scroll Indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.5 }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2"
        >
          <motion.div
            animate={{ y: [0, 10, 0] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="w-6 h-10 rounded-full border-2 border-white/20 flex items-start justify-center p-2"
          >
            <motion.div className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
          </motion.div>
        </motion.div>
      </div>
    </div>
  );
}
