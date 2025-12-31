"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  X,
  FileText,
  GitBranch,
  Shield,
  MessageSquare,
  ArrowRight,
  Sparkles,
  ChevronLeft,
  MousePointer2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter, usePathname } from "next/navigation";

const ONBOARDING_KEY = "imputable_onboarding_complete";

interface TourStep {
  title: string;
  description: string;
  icon: React.ElementType;
  gradient: string;
  highlightSelector?: string;
  requiresNavigation?: boolean;
  navigationPath?: string;
  secondarySelector?: string;
  secondaryLabel?: string;
}

const steps: TourStep[] = [
  {
    title: "Welcome to Imputable",
    description:
      "Track engineering decisions, visualize dependencies, and maintain a complete audit trail. Let's take a quick tour!",
    icon: Sparkles,
    gradient: "from-indigo-500 to-purple-600",
  },
  {
    title: "Your Decisions Hub",
    description:
      "All your engineering decisions live here. Create, search, and manage decision records in one place.",
    icon: FileText,
    gradient: "from-emerald-500 to-teal-600",
    highlightSelector: '[href="/decisions"]',
  },
  {
    title: "Mind Map Visualization",
    description:
      "See how decisions connect with an interactive mind map. AI can automatically discover relationships between decisions!",
    icon: GitBranch,
    gradient: "from-purple-500 to-pink-600",
    highlightSelector: '[href="/decisions"]',
    requiresNavigation: true,
    navigationPath: "/decisions",
    secondarySelector: "mind-map-button",
    secondaryLabel: "Mind Map",
  },
  {
    title: "Slack & Teams Integration",
    description:
      "Create decisions directly from Slack or Microsoft Teams. Capture context without leaving your workflow.",
    icon: MessageSquare,
    gradient: "from-blue-500 to-cyan-600",
    highlightSelector: '[href="/settings"]',
    requiresNavigation: true,
    navigationPath: "/settings",
    secondarySelector: "integrations-tab",
    secondaryLabel: "Integrations",
  },
  {
    title: "Complete Audit Trail",
    description:
      "Every action is logged for compliance. View the full history of all decisions and changes.",
    icon: Shield,
    gradient: "from-amber-500 to-orange-600",
    highlightSelector: '[href="/audit"]',
  },
  {
    title: "You're Ready!",
    description:
      "Start by creating your first decision. You can revisit this tour anytime from the help menu.",
    icon: Sparkles,
    gradient: "from-rose-500 to-red-600",
  },
];

type Phase =
  | "idle"
  | "transitioning"
  | "cursor-animating"
  | "navigating"
  | "arriving";

export function WelcomeModal() {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [highlightRect, setHighlightRect] = useState<DOMRect | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });
  const [showCursor, setShowCursor] = useState(false);
  const [hasNavigated, setHasNavigated] = useState(false);

  const router = useRouter();
  const pathname = usePathname();
  const animationRef = useRef<number | null>(null);
  const timeoutRefs = useRef<NodeJS.Timeout[]>([]);

  const step = steps[currentStep];
  const isCentered = !step.highlightSelector || !highlightRect;
  const isLastStep = currentStep === steps.length - 1;
  const isFirstStep = currentStep === 0;
  const Icon = step.icon;

  // Cleanup all timeouts
  const clearTimeouts = useCallback(() => {
    timeoutRefs.current.forEach(clearTimeout);
    timeoutRefs.current = [];
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
  }, []);

  // Add timeout with tracking
  const addTimeout = useCallback((fn: () => void, delay: number) => {
    const id = setTimeout(fn, delay);
    timeoutRefs.current.push(id);
    return id;
  }, []);

  // Find element by selector or data attribute
  const findElement = useCallback((selector: string): HTMLElement | null => {
    if (!selector) return null;

    // First try data-onboarding attribute (most reliable)
    const dataEl = document.querySelector<HTMLElement>(
      `[data-onboarding="${selector}"]`,
    );
    if (dataEl) return dataEl;

    // Direct CSS selector
    try {
      const el = document.querySelector<HTMLElement>(selector);
      if (el) return el;
    } catch {
      // Invalid selector, try text search
    }

    // Fallback: Find Mind Map button by text
    if (selector === "mind-map-button") {
      const allButtons = document.querySelectorAll("button");
      for (let i = 0; i < allButtons.length; i++) {
        const text = allButtons[i].textContent?.trim() || "";
        if (text === "Mind Map" || text.includes("Mind Map")) {
          return allButtons[i] as HTMLElement;
        }
      }
    }

    // Fallback: Find Integrations tab by text
    if (selector === "integrations-tab") {
      const allButtons = document.querySelectorAll("button");
      for (let i = 0; i < allButtons.length; i++) {
        const text = allButtons[i].textContent?.trim() || "";
        if (text === "Integrations" || text.includes("Integrations")) {
          return allButtons[i] as HTMLElement;
        }
      }
    }

    return null;
  }, []);

  // Update highlight rectangle
  const updateHighlight = useCallback(() => {
    if (phase !== "idle") return;

    const selector =
      hasNavigated && step.secondarySelector
        ? step.secondarySelector
        : step.highlightSelector;

    if (!selector) {
      setHighlightRect(null);
      return;
    }

    const el = findElement(selector);
    if (el) {
      const rect = el.getBoundingClientRect();
      setHighlightRect(rect);
    } else {
      setHighlightRect(null);
    }
  }, [step, hasNavigated, findElement, phase]);

  // Initialize
  useEffect(() => {
    if (typeof window !== "undefined") {
      const completed = localStorage.getItem(ONBOARDING_KEY);
      if (!completed) {
        addTimeout(() => setIsOpen(true), 300);
      }
    }
    return clearTimeouts;
  }, [addTimeout, clearTimeouts]);

  // Update highlight on changes
  useEffect(() => {
    if (isOpen && phase === "idle") {
      addTimeout(updateHighlight, 100);
      window.addEventListener("resize", updateHighlight);
      window.addEventListener("scroll", updateHighlight);
      return () => {
        window.removeEventListener("resize", updateHighlight);
        window.removeEventListener("scroll", updateHighlight);
      };
    }
  }, [isOpen, currentStep, phase, hasNavigated, updateHighlight, addTimeout]);

  // Handle page arrival after navigation
  useEffect(() => {
    if (phase === "navigating" && step.navigationPath) {
      const isOnTargetPage =
        pathname === step.navigationPath ||
        pathname.startsWith(step.navigationPath + "/");

      if (isOnTargetPage) {
        setPhase("arriving");
        // Wait for page to render, then find secondary element
        addTimeout(() => {
          setHasNavigated(true);
          setShowCursor(false);
          setPhase("idle");
          addTimeout(updateHighlight, 200);
        }, 600);
      }
    }
  }, [pathname, phase, step.navigationPath, addTimeout, updateHighlight]);

  const completeOnboarding = useCallback(() => {
    clearTimeouts();
    localStorage.setItem(ONBOARDING_KEY, "true");
    setIsOpen(false);
  }, [clearTimeouts]);

  const animateCursorTo = useCallback(
    (targetEl: HTMLElement, onComplete: () => void) => {
      const rect = targetEl.getBoundingClientRect();
      const targetX = rect.left + rect.width / 2;
      const targetY = rect.top + rect.height / 2;

      // Start from center
      const startX = window.innerWidth / 2;
      const startY = window.innerHeight / 2;
      setCursorPos({ x: startX, y: startY });
      setShowCursor(true);

      // Animate to target
      addTimeout(() => {
        setCursorPos({ x: targetX, y: targetY });

        // Click effect then complete
        addTimeout(() => {
          onComplete();
        }, 600);
      }, 50);
    },
    [addTimeout],
  );

  const goToStep = useCallback(
    (nextStepIndex: number) => {
      if (nextStepIndex < 0 || nextStepIndex >= steps.length) return;

      clearTimeouts();
      const nextStep = steps[nextStepIndex];

      setPhase("transitioning");
      setHighlightRect(null);

      addTimeout(() => {
        setCurrentStep(nextStepIndex);
        setHasNavigated(false);

        if (nextStep.requiresNavigation && nextStep.navigationPath) {
          // Find element to animate cursor to
          const targetEl = findElement(nextStep.highlightSelector || "");

          if (targetEl) {
            setPhase("cursor-animating");
            animateCursorTo(targetEl, () => {
              setPhase("navigating");
              router.push(nextStep.navigationPath!);
            });
          } else {
            // No element found, just navigate
            setPhase("navigating");
            router.push(nextStep.navigationPath);
          }
        } else {
          // Simple step change
          setPhase("idle");
        }
      }, 200);
    },
    [clearTimeouts, addTimeout, findElement, animateCursorTo, router],
  );

  const handleNext = () => {
    if (isLastStep) {
      completeOnboarding();
      router.push("/decisions/new");
    } else {
      goToStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      clearTimeouts();
      setPhase("transitioning");
      setHighlightRect(null);
      setShowCursor(false);

      addTimeout(() => {
        setCurrentStep(currentStep - 1);
        setHasNavigated(false);
        router.push("/dashboard");

        addTimeout(() => {
          setPhase("idle");
        }, 200);
      }, 150);
    }
  };

  const handleSkip = () => {
    completeOnboarding();
    router.push("/dashboard");
  };

  if (!isOpen) return null;

  const showModal = phase === "idle" || phase === "transitioning";
  const modalOpacity = phase === "idle" ? 1 : 0;

  // Calculate modal position
  const getModalStyle = (): React.CSSProperties => {
    if (isCentered) {
      return {
        position: "fixed",
        top: "50%",
        left: "50%",
        transform: `translate(-50%, -50%) scale(${modalOpacity})`,
        opacity: modalOpacity,
      };
    }

    if (!highlightRect) {
      return {
        position: "fixed",
        top: "50%",
        left: "50%",
        transform: `translate(-50%, -50%) scale(${modalOpacity})`,
        opacity: modalOpacity,
      };
    }

    // Position to the right of highlighted element
    const modalWidth = 360;
    const padding = 20;
    let left = highlightRect.right + padding;
    let top = highlightRect.top + highlightRect.height / 2;

    // Keep within viewport
    if (left + modalWidth > window.innerWidth - 20) {
      left = highlightRect.left - modalWidth - padding;
    }

    return {
      position: "fixed",
      top: top,
      left: left,
      transform: `translateY(-50%) scale(${modalOpacity === 1 ? 1 : 0.95})`,
      opacity: modalOpacity,
    };
  };

  return (
    <div className="fixed inset-0 z-[9999] pointer-events-none">
      {/* Backdrop - semi-transparent with blur */}
      <div
        className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity duration-300 pointer-events-auto"
        style={{ opacity: phase === "cursor-animating" ? 0.8 : 1 }}
        onClick={(e) => e.stopPropagation()}
      />

      {/* Spotlight effect for highlighted element */}
      {highlightRect && phase === "idle" && (
        <>
          {/* Bright spotlight cutout */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background: `radial-gradient(ellipse ${highlightRect.width + 80}px ${highlightRect.height + 80}px at ${highlightRect.left + highlightRect.width / 2}px ${highlightRect.top + highlightRect.height / 2}px, transparent 0%, transparent 50%, rgba(15, 23, 42, 0.85) 100%)`,
            }}
          />

          {/* Glowing border around element */}
          <div
            className="absolute pointer-events-none z-[10000] transition-all duration-300"
            style={{
              top: highlightRect.top - 6,
              left: highlightRect.left - 6,
              width: highlightRect.width + 12,
              height: highlightRect.height + 12,
              borderRadius: 12,
              border: "2px solid rgba(255, 255, 255, 0.9)",
              boxShadow: `
                0 0 0 4px rgba(99, 102, 241, 0.4),
                0 0 20px 8px rgba(99, 102, 241, 0.5),
                0 0 40px 16px rgba(99, 102, 241, 0.3),
                inset 0 0 20px rgba(255, 255, 255, 0.1)
              `,
              animation: "pulse-glow 2s ease-in-out infinite",
            }}
          />

          {/* Inner bright overlay on the element */}
          <div
            className="absolute pointer-events-none z-[9999]"
            style={{
              top: highlightRect.top,
              left: highlightRect.left,
              width: highlightRect.width,
              height: highlightRect.height,
              borderRadius: 8,
              background: "rgba(255, 255, 255, 0.08)",
              backdropFilter: "brightness(1.2)",
            }}
          />
        </>
      )}

      {/* Animated cursor */}
      {showCursor && (
        <div
          className="fixed pointer-events-none z-[10003] transition-all duration-500 ease-out"
          style={{
            left: cursorPos.x,
            top: cursorPos.y,
            transform: "translate(-8px, -4px)",
          }}
        >
          <MousePointer2
            className="w-8 h-8 text-white drop-shadow-lg"
            fill="white"
            strokeWidth={1}
          />
          {/* Click ripple effect */}
          <div
            className="absolute top-1 left-1 w-6 h-6 rounded-full bg-white/40 animate-ping"
            style={{ animationDuration: "1s" }}
          />
        </div>
      )}

      {/* Modal Card */}
      {showModal && (
        <div
          className="pointer-events-auto bg-white rounded-2xl shadow-2xl w-[360px] overflow-hidden transition-all duration-300 ease-out z-[10001]"
          style={getModalStyle()}
        >
          {/* Arrow pointing to highlighted element */}
          {!isCentered && highlightRect && (
            <div className="absolute w-3 h-3 bg-white rotate-45 -left-1.5 top-1/2 -translate-y-1/2 shadow-sm" />
          )}

          {/* Gradient header */}
          <div className={`bg-gradient-to-r ${step.gradient} px-6 py-5`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center">
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-white">
                    {step.title}
                  </h2>
                  <div className="text-white/70 text-xs">
                    Step {currentStep + 1} of {steps.length}
                  </div>
                </div>
              </div>
              <button
                onClick={handleSkip}
                className="p-2 rounded-lg hover:bg-white/20 transition-colors"
                aria-label="Close"
              >
                <X className="w-4 h-4 text-white/80" />
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="p-5">
            <p className="text-gray-600 text-sm leading-relaxed mb-5">
              {step.description}
            </p>

            {/* Progress bar */}
            <div className="flex gap-1.5 mb-5">
              {steps.map((_, i) => (
                <div
                  key={i}
                  className={`h-1 flex-1 rounded-full transition-all duration-300 ${
                    i < currentStep
                      ? "bg-indigo-500"
                      : i === currentStep
                        ? "bg-indigo-500"
                        : "bg-gray-200"
                  }`}
                />
              ))}
            </div>

            {/* Navigation buttons */}
            <div className="flex gap-2">
              {!isFirstStep && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleBack}
                  className="gap-1 text-gray-600"
                  disabled={phase !== "idle"}
                >
                  <ChevronLeft className="w-4 h-4" />
                  Back
                </Button>
              )}

              <Button
                onClick={handleNext}
                size="sm"
                className={`flex-1 gap-2 bg-gradient-to-r ${step.gradient} hover:opacity-90 border-0 text-white`}
                disabled={phase !== "idle"}
              >
                {isFirstStep
                  ? "Start Tour"
                  : isLastStep
                    ? "Create First Decision"
                    : "Next"}
                <ArrowRight className="w-4 h-4" />
              </Button>
            </div>

            {/* Skip link */}
            {!isLastStep && (
              <button
                onClick={handleSkip}
                className="w-full mt-3 text-xs text-gray-400 hover:text-gray-600 transition-colors"
              >
                Skip tour
              </button>
            )}
          </div>
        </div>
      )}

      {/* Loading indicator during navigation */}
      {(phase === "navigating" || phase === "arriving") && (
        <div className="fixed inset-0 flex items-center justify-center z-[10002] pointer-events-none">
          <div className="bg-white/90 backdrop-blur-sm rounded-2xl px-6 py-4 shadow-xl flex items-center gap-3">
            <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-gray-600">
              {phase === "arriving" ? "Almost there..." : "Navigating..."}
            </span>
          </div>
        </div>
      )}

      {/* CSS for pulse animation */}
      <style jsx global>{`
        @keyframes pulse-glow {
          0%,
          100% {
            box-shadow:
              0 0 0 4px rgba(99, 102, 241, 0.4),
              0 0 20px 8px rgba(99, 102, 241, 0.5),
              0 0 40px 16px rgba(99, 102, 241, 0.3),
              inset 0 0 20px rgba(255, 255, 255, 0.1);
          }
          50% {
            box-shadow:
              0 0 0 6px rgba(99, 102, 241, 0.5),
              0 0 30px 12px rgba(99, 102, 241, 0.6),
              0 0 60px 24px rgba(99, 102, 241, 0.4),
              inset 0 0 30px rgba(255, 255, 255, 0.15);
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

  const resetOnboarding = useCallback(() => {
    localStorage.removeItem(ONBOARDING_KEY);
    setShouldShowOnboarding(true);
    window.location.reload();
  }, []);

  return { shouldShowOnboarding, resetOnboarding };
}
