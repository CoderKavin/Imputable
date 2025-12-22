"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { LandingNavbar } from "@/components/landing/navbar";
import { SpotlightHero } from "@/components/landing/spotlight-hero";
import { BentoGrid } from "@/components/landing/bento-grid";
import { FeaturesSection } from "@/components/landing/features-section";
import { CTASection } from "@/components/landing/cta-section";
import { Footer } from "@/components/landing/footer";

/**
 * Landing Page
 *
 * Public page that shows the product value proposition.
 * If user is already signed in, redirect to dashboard.
 */
export default function Home() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    // If already signed in, redirect to dashboard
    if (!loading && user) {
      router.replace("/dashboard");
    }
  }, [user, loading, router]);

  // Show loading state while checking auth
  if (loading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-white/20 border-t-white rounded-full animate-spin" />
      </div>
    );
  }

  // If user is signed in, don't render (will redirect)
  if (user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-black text-white overflow-x-hidden">
      {/* Ambient background effects */}
      <div className="fixed inset-0 pointer-events-none">
        {/* Top left glow */}
        <div
          className="absolute -top-40 -left-40 w-96 h-96 bg-cyan-500/20 rounded-full blur-[120px] animate-pulse-glow"
          style={{ animationDelay: "0s" }}
        />
        {/* Top right glow */}
        <div
          className="absolute -top-20 right-20 w-80 h-80 bg-purple-500/20 rounded-full blur-[100px] animate-pulse-glow"
          style={{ animationDelay: "1s" }}
        />
        {/* Bottom center glow */}
        <div
          className="absolute bottom-20 left-1/2 -translate-x-1/2 w-[600px] h-60 bg-pink-500/10 rounded-full blur-[150px] animate-pulse-glow"
          style={{ animationDelay: "2s" }}
        />
      </div>

      {/* Noise texture overlay */}
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.015]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* Content */}
      <div className="relative z-10">
        <LandingNavbar />
        <SpotlightHero />
        <BentoGrid />
        <FeaturesSection />
        <CTASection />
        <Footer />
      </div>
    </div>
  );
}
