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
  // For multi-phase steps (Mind Map, Slack/Teams)
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
  const [phase, setPhase] = useState<"moving" | "clicking" | "done">("moving");

  useEffect(() => {
    const targetX = toRect.left + toRect.width / 2;
    const targetY = toRect.top + toRect.height / 2;

    // Start animation after a brief delay
    const moveTimer = setTimeout(() => {
      setPosition({ x: targetX, y: targetY });
    }, 300);

    // Click animation after cursor arrives
    const clickTimer = setTimeout(() => {
      setPhase("clicking");
      setIsClicking(true);
    }, 1100);

    // Complete after click
    const completeTimer = setTimeout(() => {
      setIsClicking(false);
      setPhase("done");
      onComplete();
    }, 1500);

    return () => {
      clearTimeout(moveTimer);
      clearTimeout(clickTimer);
      clearTimeout(completeTimer);
    };
  }, [toRect, onComplete]);

  return (
    <div
      className="fixed z-[400] pointer-events-none transition-all duration-700 ease-out"
      style={{
        left: position.x,
        top: position.y,
        transform: `translate(-50%, -50%) ${isClicking ? "scale(0.8)" : "scale(1)"}`,
      }}
    >
      <div className={`relative ${isClicking ? "animate-pulse" : ""}`}>
        <MousePointer2
          className="w-8 h-8 text-white drop-shadow-lg"
          fill="white"
          style={{ filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.3))" }}
        />
        {isClicking && (
          <div className="absolute -inset-4 rounded-full bg-indigo-500/30 animate-ping" />
        )}
      </div>
    </div>
  );
}

export function WelcomeModal({ onComplete }: WelcomeModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [stepPhase, setStepPhase] = useState<StepPhase>("highlight");
  const [highlightRect, setHighlightRect] = useState<DOMRect | null>(null);
  const [secondaryRect, setSecondaryRect] = useState<DOMRect | null>(null);
  const [showCursor, setShowCursor] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  const step = steps[currentStep];

  // Find and measure the highlighted element
  const updateHighlight = useCallback(() => {
    if (stepPhase === "show-target" && step.secondarySelector) {
      // Try to find the secondary element (Mind Map button, Integrations tab)
      const selectors = step.secondarySelector.split(", ");
      for (const selector of selectors) {
        try {
          const element = document.querySelector(selector);
          if (element) {
            setSecondaryRect(element.getBoundingClientRect());
            setHighlightRect(null);
            return;
          }
        } catch (e) {
          // Invalid selector, try next
        }
      }
      // Fallback: find by text content for Mind Map
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
      // Fallback for integrations tab
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

  // Handle navigation for multi-phase steps
  useEffect(() => {
    if (
      stepPhase === "animate-cursor" &&
      step.requiresNavigation &&
      step.navigationPath
    ) {
      // Navigate after cursor animation completes
      const timer = setTimeout(() => {
        router.push(step.navigationPath!);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [stepPhase, step, router]);

  // After navigation, show the secondary target
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
        updateHighlight();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [pathname, step, stepPhase, updateHighlight]);

  const handleComplete = () => {
    localStorage.setItem(ONBOARDING_KEY, "true");
    setIsOpen(false);
    router.push("/dashboard");
    onComplete?.();
  };

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      const nextStep = steps[currentStep + 1];

      // Move to next step
      setCurrentStep(currentStep + 1);

      // If next step requires navigation, start cursor animation immediately
      if (nextStep.requiresNavigation) {
        setStepPhase("animate-cursor");
        setShowCursor(true);
      } else {
        setStepPhase("highlight");
        setShowCursor(false);
      }
    } else {
      handleComplete();
    }
  };

  const handleSkip = () => {
    handleComplete();
  };

  const handleGetStarted = () => {
    handleComplete();
    router.push("/decisions/new");
  };

  const handleCursorComplete = () => {
    // Cursor finished animating to sidebar, now navigate
    if (step.navigationPath) {
      router.push(step.navigationPath);
    }
  };

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

    const padding = 16;
    const tooltipWidth = 380;

    return {
      position: "fixed",
      top: activeRect.top + activeRect.height / 2,
      left: activeRect.right + padding + 20,
      transform: "translateY(-50%)",
      maxWidth: tooltipWidth,
    };
  };

  return (
    <div className="fixed inset-0 z-[300]">
      {/* Backdrop */}
      {isCentered ? (
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      ) : (
        <>
          <div className="absolute inset-0 bg-black/60" />
          {activeRect && (
            <>
              <div
                className="absolute z-[301] rounded-2xl ring-4 ring-indigo-500 ring-offset-4 ring-offset-transparent bg-transparent pointer-events-none transition-all duration-300"
                style={{
                  top: activeRect.top - 8,
                  left: activeRect.left - 8,
                  width: activeRect.width + 16,
                  height: activeRect.height + 16,
                  boxShadow: "0 0 0 9999px rgba(0, 0, 0, 0.6)",
                }}
              />
              <div
                className="absolute z-[300] rounded-2xl animate-ping bg-indigo-500/30 pointer-events-none"
                style={{
                  top: activeRect.top - 8,
                  left: activeRect.left - 8,
                  width: activeRect.width + 16,
                  height: activeRect.height + 16,
                }}
              />
            </>
          )}
        </>
      )}

      {/* Animated cursor for multi-phase steps */}
      {showCursor && highlightRect && (
        <AnimatedCursor
          fromRect={
            new DOMRect(window.innerWidth / 2, window.innerHeight / 2, 0, 0)
          }
          toRect={highlightRect}
          onComplete={handleCursorComplete}
        />
      )}

      {/* Tooltip/Modal */}
      <div
        className="z-[302] bg-white rounded-3xl shadow-2xl overflow-hidden"
        style={getTooltipStyle()}
      >
        {!isCentered && activeRect && (
          <div
            className="absolute w-4 h-4 bg-white transform rotate-45 -left-2 top-1/2 -translate-y-1/2"
            style={{ boxShadow: "-2px 2px 4px rgba(0,0,0,0.1)" }}
          />
        )}

        <button
          onClick={handleSkip}
          className="absolute top-4 right-4 p-2 rounded-lg hover:bg-gray-100 transition-colors z-10"
        >
          <X className="w-5 h-5 text-gray-400" />
        </button>

        <div className={`p-6 ${isCentered ? "pt-10" : "pt-6"} text-center`}>
          <div
            className={`w-14 h-14 ${step.color} rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg`}
          >
            <Icon className="w-7 h-7 text-white" />
          </div>

          <h2 className="text-xl font-bold text-gray-900 mb-2">{step.title}</h2>

          <p className="text-gray-600 text-sm leading-relaxed mb-6">
            {step.description}
          </p>

          <div className="flex items-center justify-center gap-2 mb-6">
            {steps.map((_, index) => (
              <div
                key={index}
                className={`
                  h-2 rounded-full transition-all duration-300
                  ${
                    index === currentStep
                      ? "w-6 bg-indigo-500"
                      : index < currentStep
                        ? "w-2 bg-indigo-300"
                        : "w-2 bg-gray-200"
                  }
                `}
              />
            ))}
          </div>

          <div className="flex gap-3">
            {currentStep > 0 && stepPhase !== "animate-cursor" && (
              <Button
                variant="outline"
                onClick={() => {
                  setCurrentStep(currentStep - 1);
                  setStepPhase("highlight");
                  setShowCursor(false);
                  router.push("/dashboard");
                }}
                className="flex-1 rounded-xl"
                size="sm"
              >
                Back
              </Button>
            )}

            {stepPhase === "animate-cursor" ? (
              <div className="flex-1 text-sm text-gray-500 py-2">
                Navigating...
              </div>
            ) : isLastStep ? (
              <Button
                onClick={handleGetStarted}
                className="flex-1 rounded-xl bg-indigo-500 hover:bg-indigo-600"
                size="sm"
              >
                Create Your First Decision
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            ) : (
              <Button
                onClick={handleNext}
                className="flex-1 rounded-xl"
                size="sm"
              >
                {isFirstStep ? "Take a Tour" : "Next"}
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            )}
          </div>

          {!isLastStep && stepPhase !== "animate-cursor" && (
            <button
              onClick={handleSkip}
              className="mt-3 text-xs text-gray-400 hover:text-gray-600 transition-colors"
            >
              Skip tour
            </button>
          )}
        </div>
      </div>
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
