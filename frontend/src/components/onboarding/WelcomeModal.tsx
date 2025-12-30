"use client";

import { useState, useEffect, useCallback } from "react";
import {
  X,
  FileText,
  GitBranch,
  Shield,
  Bell,
  ArrowRight,
  Sparkles,
  MessageSquare,
  MousePointer2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter, usePathname } from "next/navigation";

const ONBOARDING_KEY = "imputable_onboarding_complete";

interface WelcomeModalProps {
  onComplete?: () => void;
}

type StepPhase = "highlight" | "animate-cursor" | "show-target";

interface TourStep {
  title: string;
  description: string;
  icon: React.ElementType;
  color: string;
  highlightSelector?: string;
  position?: "top" | "bottom" | "left" | "right" | "center";
  requiresNavigation?: boolean;
  navigationPath?: string;
  secondarySelector?: string;
}

const steps: TourStep[] = [
  {
    title: "Welcome to Imputable",
    description:
      "The decision tracking platform that helps engineering teams document, track, and audit their key decisions.",
    icon: Sparkles,
    color: "bg-indigo-500",
    position: "center",
  },
  {
    title: "Create Decisions",
    description:
      "This is where all your decisions live. Click here to view, search, and manage your engineering decisions.",
    icon: FileText,
    color: "bg-emerald-500",
    highlightSelector: '[href="/decisions"]',
    position: "right",
  },
  {
    title: "Visualize with Mind Map",
    description:
      "Switch to Mind Map view here to see how decisions connect. AI can automatically discover relationships!",
    icon: GitBranch,
    color: "bg-purple-500",
    highlightSelector: '[href="/decisions"]',
    position: "right",
    requiresNavigation: true,
    navigationPath: "/decisions",
    secondarySelector:
      'button:has(.lucide-git-branch), [class*="mindmap"], button:contains("Mind Map")',
  },
  {
    title: "Works Best with Slack & Teams",
    description:
      "Connect Slack or Microsoft Teams here to create decisions without leaving your workflow!",
    icon: MessageSquare,
    color: "bg-blue-500",
    highlightSelector: '[href="/settings"]',
    position: "right",
    requiresNavigation: true,
    navigationPath: "/settings",
    secondarySelector:
      '[data-tab="integrations"], button:contains("Integrations")',
  },
  {
    title: "Audit Trail",
    description:
      "Every action is logged here. View the complete history of all decisions and changes for compliance.",
    icon: Shield,
    color: "bg-amber-500",
    highlightSelector: '[href="/audit"]',
    position: "right",
  },
  {
    title: "You're All Set!",
    description:
      "Start by creating your first decision. You can always access help from the sidebar if you need guidance.",
    icon: Bell,
    color: "bg-rose-500",
    position: "center",
  },
];

// Animated cursor component
function AnimatedCursor({
  fromRect,
  toRect,
  onComplete,
}: {
  fromRect: DOMRect;
  toRect: DOMRect;
  onComplete: () => void;
}) {
  const [position, setPosition] = useState({
    x: fromRect.left + fromRect.width / 2,
    y: fromRect.top + fromRect.height / 2,
  });
  const [isClicking, setIsClicking] = useState(false);

  useEffect(() => {
    const targetX = toRect.left + toRect.width / 2;
    const targetY = toRect.top + toRect.height / 2;

    const moveTimer = setTimeout(() => {
      setPosition({ x: targetX, y: targetY });
    }, 200);

    const clickTimer = setTimeout(() => {
      setIsClicking(true);
    }, 900);

    const completeTimer = setTimeout(() => {
      setIsClicking(false);
      onComplete();
    }, 1200);

    return () => {
      clearTimeout(moveTimer);
      clearTimeout(clickTimer);
      clearTimeout(completeTimer);
    };
  }, [toRect, onComplete]);

  return (
    <div
      className="fixed z-[400] pointer-events-none"
      style={{
        left: position.x,
        top: position.y,
        transform: `translate(-50%, -50%) ${isClicking ? "scale(0.85)" : "scale(1)"}`,
        transition:
          "left 0.6s cubic-bezier(0.4, 0, 0.2, 1), top 0.6s cubic-bezier(0.4, 0, 0.2, 1), transform 0.15s ease-out",
      }}
    >
      <MousePointer2
        className="w-7 h-7 text-white"
        fill="white"
        style={{ filter: "drop-shadow(0 2px 8px rgba(0,0,0,0.4))" }}
      />
      {isClicking && (
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-indigo-400/50"
          style={{ animation: "ping 0.4s ease-out" }}
        />
      )}
    </div>
  );
}

// Smooth highlight border component
function HighlightBorder({ rect }: { rect: DOMRect }) {
  return (
    <>
      {/* Clean border highlight */}
      <div
        className="absolute z-[301] pointer-events-none"
        style={{
          top: rect.top - 6,
          left: rect.left - 6,
          width: rect.width + 12,
          height: rect.height + 12,
          borderRadius: 12,
          border: "3px solid #6366f1",
          boxShadow: "0 0 0 9999px rgba(0, 0, 0, 0.7)",
          transition: "all 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      />
      {/* Animated gradient border */}
      <div
        className="absolute z-[300] pointer-events-none"
        style={{
          top: rect.top - 8,
          left: rect.left - 8,
          width: rect.width + 16,
          height: rect.height + 16,
          borderRadius: 14,
          background: "linear-gradient(90deg, #6366f1, #8b5cf6, #6366f1)",
          backgroundSize: "200% 100%",
          animation: "shimmer 2s linear infinite",
          padding: 2,
          transition: "all 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      >
        <div
          className="w-full h-full rounded-xl"
          style={{ background: "transparent" }}
        />
      </div>
      <style jsx>{`
        @keyframes shimmer {
          0% {
            background-position: 200% 0;
          }
          100% {
            background-position: -200% 0;
          }
        }
      `}</style>
    </>
  );
}

export function WelcomeModal({ onComplete }: WelcomeModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [stepPhase, setStepPhase] = useState<StepPhase>("highlight");
  const [highlightRect, setHighlightRect] = useState<DOMRect | null>(null);
  const [secondaryRect, setSecondaryRect] = useState<DOMRect | null>(null);
  const [showCursor, setShowCursor] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  const step = steps[currentStep];

  const updateHighlight = useCallback(() => {
    if (stepPhase === "show-target" && step.secondarySelector) {
      const selectors = step.secondarySelector.split(", ");
      for (const selector of selectors) {
        try {
          const element = document.querySelector(selector);
          if (element) {
            setSecondaryRect(element.getBoundingClientRect());
            setHighlightRect(null);
            return;
          }
        } catch {
          // Invalid selector, try next
        }
      }
      if (step.title.includes("Mind Map")) {
        const buttons = Array.from(document.querySelectorAll("button"));
        for (const btn of buttons) {
          if (btn.textContent?.includes("Mind Map")) {
            setSecondaryRect(btn.getBoundingClientRect());
            setHighlightRect(null);
            return;
          }
        }
      }
      if (step.title.includes("Slack")) {
        const buttons = Array.from(document.querySelectorAll("button"));
        for (const btn of buttons) {
          if (btn.textContent?.includes("Integrations")) {
            setSecondaryRect(btn.getBoundingClientRect());
            setHighlightRect(null);
            return;
          }
        }
      }
    }

    if (step.highlightSelector) {
      const element = document.querySelector(step.highlightSelector);
      if (element) {
        setHighlightRect(element.getBoundingClientRect());
        setSecondaryRect(null);
        return;
      }
    }
    setHighlightRect(null);
    setSecondaryRect(null);
  }, [currentStep, stepPhase, step]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const completed = localStorage.getItem(ONBOARDING_KEY);
      if (!completed) {
        const timer = setTimeout(() => setIsOpen(true), 500);
        return () => clearTimeout(timer);
      }
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      updateHighlight();
      window.addEventListener("resize", updateHighlight);
      return () => window.removeEventListener("resize", updateHighlight);
    }
  }, [isOpen, currentStep, stepPhase, updateHighlight]);

  useEffect(() => {
    if (
      step.requiresNavigation &&
      step.navigationPath &&
      pathname === step.navigationPath &&
      stepPhase === "animate-cursor"
    ) {
      const timer = setTimeout(() => {
        setStepPhase("show-target");
        setShowCursor(false);
        setIsTransitioning(false);
      }, 600);
      return () => clearTimeout(timer);
    }
  }, [pathname, step, stepPhase]);

  const handleComplete = () => {
    localStorage.setItem(ONBOARDING_KEY, "true");
    setIsOpen(false);
    router.push("/dashboard");
    onComplete?.();
  };

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      const nextStep = steps[currentStep + 1];

      // Smooth transition
      setIsTransitioning(true);

      setTimeout(() => {
        setCurrentStep(currentStep + 1);

        if (nextStep.requiresNavigation) {
          setStepPhase("animate-cursor");
          setShowCursor(true);
        } else {
          setStepPhase("highlight");
          setShowCursor(false);
          setTimeout(() => setIsTransitioning(false), 300);
        }
      }, 150);
    } else {
      handleComplete();
    }
  };

  const handleBack = () => {
    setIsTransitioning(true);
    setTimeout(() => {
      setCurrentStep(currentStep - 1);
      setStepPhase("highlight");
      setShowCursor(false);
      router.push("/dashboard");
      setTimeout(() => setIsTransitioning(false), 300);
    }, 150);
  };

  const handleSkip = () => {
    handleComplete();
  };

  const handleGetStarted = () => {
    handleComplete();
    router.push("/decisions/new");
  };

  const handleCursorComplete = useCallback(() => {
    if (step.navigationPath && pathname !== step.navigationPath) {
      router.push(step.navigationPath);
    }
  }, [step.navigationPath, pathname, router]);

  if (!isOpen) return null;

  const isLastStep = currentStep === steps.length - 1;
  const isFirstStep = currentStep === 0;
  const activeRect = secondaryRect || highlightRect;
  const isCentered = step.position === "center" || !activeRect;
  const Icon = step.icon;

  const getTooltipStyle = (): React.CSSProperties => {
    if (isCentered || !activeRect) {
      return {
        position: "fixed",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
      };
    }

    return {
      position: "fixed",
      top: activeRect.top + activeRect.height / 2,
      left: activeRect.right + 32,
      transform: "translateY(-50%)",
      maxWidth: 360,
    };
  };

  return (
    <div className="fixed inset-0 z-[300]">
      {/* Backdrop with smooth transition */}
      <div
        className="absolute inset-0 bg-black/70 transition-opacity duration-500"
        style={{ opacity: isTransitioning ? 0.5 : 1 }}
      />

      {/* Highlight border */}
      {!isCentered && activeRect && <HighlightBorder rect={activeRect} />}

      {/* Animated cursor */}
      {showCursor && highlightRect && (
        <AnimatedCursor
          fromRect={
            new DOMRect(window.innerWidth / 2, window.innerHeight / 2, 0, 0)
          }
          toRect={highlightRect}
          onComplete={handleCursorComplete}
        />
      )}

      {/* Modal card with smooth transitions */}
      <div
        className="z-[302] bg-white rounded-2xl shadow-2xl overflow-hidden transition-all duration-300"
        style={{
          ...getTooltipStyle(),
          opacity: isTransitioning ? 0 : 1,
          transform: `${isCentered || !activeRect ? "translate(-50%, -50%)" : "translateY(-50%)"} scale(${isTransitioning ? 0.95 : 1})`,
        }}
      >
        {/* Arrow pointer for non-centered modals */}
        {!isCentered && activeRect && (
          <div
            className="absolute w-3 h-3 bg-white transform rotate-45 -left-1.5 top-1/2 -translate-y-1/2 transition-opacity duration-300"
            style={{
              boxShadow: "-2px 2px 4px rgba(0,0,0,0.08)",
              opacity: isTransitioning ? 0 : 1,
            }}
          />
        )}

        <button
          onClick={handleSkip}
          className="absolute top-3 right-3 p-2 rounded-lg hover:bg-gray-100 transition-colors z-10"
        >
          <X className="w-4 h-4 text-gray-400" />
        </button>

        <div className="p-6 text-center">
          {/* Icon with color transition */}
          <div
            className={`w-12 h-12 ${step.color} rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg transition-all duration-300`}
            style={{ transform: isTransitioning ? "scale(0.9)" : "scale(1)" }}
          >
            <Icon className="w-6 h-6 text-white" />
          </div>

          <h2 className="text-lg font-semibold text-gray-900 mb-2 transition-opacity duration-200">
            {step.title}
          </h2>

          <p className="text-gray-500 text-sm leading-relaxed mb-5 transition-opacity duration-200">
            {step.description}
          </p>

          {/* Progress dots */}
          <div className="flex items-center justify-center gap-1.5 mb-5">
            {steps.map((_, index) => (
              <div
                key={index}
                className="rounded-full transition-all duration-300 ease-out"
                style={{
                  width: index === currentStep ? 20 : 6,
                  height: 6,
                  backgroundColor:
                    index === currentStep
                      ? "#6366f1"
                      : index < currentStep
                        ? "#a5b4fc"
                        : "#e5e7eb",
                }}
              />
            ))}
          </div>

          {/* Buttons */}
          <div className="flex gap-2">
            {currentStep > 0 && stepPhase !== "animate-cursor" && (
              <Button
                variant="outline"
                onClick={handleBack}
                className="flex-1 rounded-lg h-9 text-sm"
                size="sm"
              >
                Back
              </Button>
            )}

            {stepPhase === "animate-cursor" ? (
              <div className="flex-1 flex items-center justify-center text-sm text-gray-400 py-2">
                <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mr-2" />
                Loading...
              </div>
            ) : isLastStep ? (
              <Button
                onClick={handleGetStarted}
                className="flex-1 rounded-lg h-9 text-sm bg-indigo-500 hover:bg-indigo-600"
                size="sm"
              >
                Get Started
                <ArrowRight className="w-4 h-4 ml-1.5" />
              </Button>
            ) : (
              <Button
                onClick={handleNext}
                className="flex-1 rounded-lg h-9 text-sm"
                size="sm"
              >
                {isFirstStep ? "Take a Tour" : "Next"}
                <ArrowRight className="w-4 h-4 ml-1.5" />
              </Button>
            )}
          </div>

          {!isLastStep && stepPhase !== "animate-cursor" && (
            <button
              onClick={handleSkip}
              className="mt-3 text-xs text-gray-400 hover:text-gray-500 transition-colors"
            >
              Skip tour
            </button>
          )}
        </div>
      </div>

      {/* Global styles for animations */}
      <style jsx global>{`
        @keyframes shimmer {
          0% {
            background-position: 200% 0;
          }
          100% {
            background-position: -200% 0;
          }
        }
        @keyframes ping {
          0% {
            transform: translate(-50%, -50%) scale(1);
            opacity: 1;
          }
          100% {
            transform: translate(-50%, -50%) scale(2);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
}

export function useOnboardingStatus() {
  const [shouldShowOnboarding, setShouldShowOnboarding] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const completed = localStorage.getItem(ONBOARDING_KEY);
      setShouldShowOnboarding(!completed);
    }
  }, []);

  const resetOnboarding = () => {
    localStorage.removeItem(ONBOARDING_KEY);
    setShouldShowOnboarding(true);
  };

  return { shouldShowOnboarding, resetOnboarding };
}
