"use client";

import { useRef, useState } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";

interface TiltCardProps {
  children: React.ReactNode;
  className?: string;
  glowColor?: string;
}

export function TiltCard({
  children,
  className = "",
  glowColor = "cyan",
}: TiltCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);

  // Mouse position relative to card center (-0.5 to 0.5)
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  // Smooth spring animation
  const springConfig = { stiffness: 300, damping: 30 };
  const rotateX = useSpring(useTransform(mouseY, [-0.5, 0.5], [15, -15]), springConfig);
  const rotateY = useSpring(useTransform(mouseX, [-0.5, 0.5], [-15, 15]), springConfig);

  // Glare effect position
  const glareX = useSpring(useTransform(mouseX, [-0.5, 0.5], [0, 100]), springConfig);
  const glareY = useSpring(useTransform(mouseY, [-0.5, 0.5], [0, 100]), springConfig);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    mouseX.set(x);
    mouseY.set(y);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    mouseX.set(0);
    mouseY.set(0);
  };

  const glowColors: Record<string, string> = {
    cyan: "rgba(6, 182, 212, 0.4)",
    purple: "rgba(139, 92, 246, 0.4)",
    pink: "rgba(236, 72, 153, 0.4)",
    green: "rgba(34, 197, 94, 0.4)",
  };

  return (
    <motion.div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={handleMouseLeave}
      style={{
        rotateX,
        rotateY,
        transformStyle: "preserve-3d",
        perspective: 1000,
      }}
      className={`relative group ${className}`}
    >
      {/* Card Background with Glass Effect */}
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/10 to-white/5 backdrop-blur-xl border border-white/10" />

      {/* Animated Border Glow */}
      <motion.div
        className="absolute -inset-px rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"
        style={{
          background: `linear-gradient(135deg, ${glowColors[glowColor]}, transparent 50%)`,
        }}
      />

      {/* Glare Effect */}
      <motion.div
        className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-30 transition-opacity duration-300 pointer-events-none overflow-hidden"
        style={{
          background: useTransform(
            [glareX, glareY],
            ([x, y]) =>
              `radial-gradient(circle at ${x}% ${y}%, rgba(255,255,255,0.3) 0%, transparent 50%)`
          ),
        }}
      />

      {/* Content with Z-transform for depth */}
      <motion.div
        className="relative z-10 p-6"
        style={{
          transformStyle: "preserve-3d",
          transform: isHovered ? "translateZ(30px)" : "translateZ(0px)",
          transition: "transform 0.3s ease-out",
        }}
      >
        {children}
      </motion.div>
    </motion.div>
  );
}

// Feature Card that uses TiltCard
interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  glowColor?: string;
}

export function FeatureCard({
  icon,
  title,
  description,
  glowColor = "cyan",
}: FeatureCardProps) {
  const glowBgColors: Record<string, string> = {
    cyan: "bg-cyan-500/20",
    purple: "bg-purple-500/20",
    pink: "bg-pink-500/20",
    green: "bg-green-500/20",
  };

  const glowTextColors: Record<string, string> = {
    cyan: "text-cyan-400",
    purple: "text-purple-400",
    pink: "text-pink-400",
    green: "text-green-400",
  };

  return (
    <TiltCard glowColor={glowColor} className="h-full">
      <div className="flex flex-col h-full">
        {/* Icon with glow */}
        <div
          className={`w-14 h-14 rounded-xl ${glowBgColors[glowColor]} flex items-center justify-center mb-5`}
          style={{ transform: "translateZ(20px)" }}
        >
          <div className={glowTextColors[glowColor]}>{icon}</div>
        </div>

        {/* Title */}
        <h3
          className="text-xl font-semibold text-white mb-3"
          style={{ transform: "translateZ(15px)" }}
        >
          {title}
        </h3>

        {/* Description */}
        <p
          className="text-gray-400 leading-relaxed"
          style={{ transform: "translateZ(10px)" }}
        >
          {description}
        </p>
      </div>
    </TiltCard>
  );
}
