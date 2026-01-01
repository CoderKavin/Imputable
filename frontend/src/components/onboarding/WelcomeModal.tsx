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
const ONBOARDING_STEP_KEY = "imputable_onboarding_step";

interface TourStep {
  title: string;
  description: string;
  icon: React.ElementType;
  gradient: string;
  highlightSelector?: string;
  navigateTo?: string;
  cursorTargetSelector?: string; // What the cursor should click (if different from highlight)
  showCursorAnimation?: boolean; // Whether to show cursor animation for this step
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
    highlightSelector: '[data-onboarding="decisions-link"]',
  },
  {
    title: "Mind Map Visualization",
    description:
      "Switch to Mind Map view to see how decisions connect. AI can automatically discover relationships!",
    icon: GitBranch,
    gradient: "from-purple-500 to-pink-600",
    highlightSelector: '[data-onboarding="mind-map-button"]',
    navigateTo: "/decisions",
    cursorTargetSelector: '[data-onboarding="settings-link"]', // Cursor clicks Settings to go to next step
    showCursorAnimation: true,
  },
  {
    title: "Slack & Teams Integration",
    description:
      "Connect Slack or Microsoft Teams to create decisions without leaving your workflow.",
    icon: MessageSquare,
    gradient: "from-blue-500 to-cyan-600",
    highlightSelector: '[data-onboarding="integrations-tab"]',
    navigateTo: "/settings",
  },
  {
    title: "Complete Audit Trail",
    description:
      "Every action is logged for compliance. View the full history of all decisions and changes.",
    icon: Shield,
    gradient: "from-amber-500 to-orange-600",
    highlightSelector: '[data-onboarding="audit-link"]',
    navigateTo: "/dashboard",
  },
  {
    title: "You're Ready!",
    description:
      "Start by creating your first decision. You can revisit this tour anytime from settings.",
    icon: Sparkles,
    gradient: "from-rose-500 to-red-600",
  },
];

export function WelcomeModal() {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem(ONBOARDING_STEP_KEY);
      return saved ? parseInt(saved, 10) : 0;
    }
    return 0;
  });
  const [highlightRect, setHighlightRect] = useState<DOMRect | null>(null);
  const [isNavigating, setIsNavigating] = useState(false);
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });
  const [showCursor, setShowCursor] = useState(false);
  const [cursorClicking, setCursorClicking] = useState(false);

  const router = useRouter();
  const pathname = usePathname();
  const retryRef = useRef<NodeJS.Timeout | null>(null);
  const expectedPathRef = useRef<string | null>(null);

  const step = steps[currentStep];
  const isLastStep = currentStep === steps.length - 1;
  const isFirstStep = currentStep === 0;
  const Icon = step.icon;

  // Save step to sessionStorage whenever it changes
  useEffect(() => {
    if (typeof window !== "undefined") {
      sessionStorage.setItem(ONBOARDING_STEP_KEY, currentStep.toString());
    }
  }, [currentStep]);

  // Find and highlight element
  const findAndHighlight = useCallback(() => {
    if (!step.highlightSelector) {
      setHighlightRect(null);
      return true;
    }

    const el = document.querySelector<HTMLElement>(step.highlightSelector);
    if (el) {
      const rect = el.getBoundingClientRect();
      setHighlightRect(rect);
      return true;
    }
    setHighlightRect(null);
    return false;
  }, [step.highlightSelector]);

  // Check onboarding status on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const completed = localStorage.getItem(ONBOARDING_KEY);
      if (!completed) {
        const timer = setTimeout(() => setIsOpen(true), 500);
        return () => clearTimeout(timer);
      }
    }
  }, []);

  // Handle navigation completion
  useEffect(() => {
    if (isNavigating && expectedPathRef.current) {
      if (
        pathname === expectedPathRef.current ||
        pathname.startsWith(expectedPathRef.current + "/")
      ) {
        expectedPathRef.current = null;

        let attempts = 0;
        const maxAttempts = 30;

        const tryFind = () => {
          attempts++;
          const found = findAndHighlight();

          if (found || attempts >= maxAttempts) {
            setShowCursor(false);
            setCursorClicking(false);
            setIsNavigating(false);
            if (retryRef.current) {
              clearInterval(retryRef.current);
              retryRef.current = null;
            }
          }
        };

        tryFind();
        if (retryRef.current) clearInterval(retryRef.current);
        retryRef.current = setInterval(tryFind, 100);
      }
    }
  }, [pathname, isNavigating, findAndHighlight]);

  // Update highlight when step changes (for non-navigation steps)
  useEffect(() => {
    if (!isOpen || isNavigating) return;

    if (retryRef.current) {
      clearInterval(retryRef.current);
      retryRef.current = null;
    }

    let attempts = 0;
    const tryFind = () => {
      attempts++;
      const found = findAndHighlight();
      if (found || attempts >= 20) {
        if (retryRef.current) {
          clearInterval(retryRef.current);
          retryRef.current = null;
        }
      }
    };

    tryFind();
    retryRef.current = setInterval(tryFind, 100);

    const handleUpdate = () => {
      if (!isNavigating) findAndHighlight();
    };
    window.addEventListener("resize", handleUpdate);
    window.addEventListener("scroll", handleUpdate, true);

    return () => {
      if (retryRef.current) {
        clearInterval(retryRef.current);
        retryRef.current = null;
      }
      window.removeEventListener("resize", handleUpdate);
      window.removeEventListener("scroll", handleUpdate, true);
    };
  }, [isOpen, currentStep, isNavigating, findAndHighlight]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (retryRef.current) {
        clearInterval(retryRef.current);
      }
    };
  }, []);

  const completeOnboarding = useCallback(() => {
    if (retryRef.current) clearInterval(retryRef.current);
    localStorage.setItem(ONBOARDING_KEY, "true");
    sessionStorage.removeItem(ONBOARDING_STEP_KEY);
    setIsOpen(false);
  }, []);

  const animateCursorAndNavigate = useCallback(
    (targetStep: TourStep, stepIndex: number) => {
      // Only show cursor animation if the CURRENT step has showCursorAnimation enabled
      const shouldShowCursor = step.showCursorAnimation === true;

      // Find the element to animate cursor to (use cursorTargetSelector if available, else highlightSelector)
      const cursorSelector =
        step.cursorTargetSelector || step.highlightSelector;
      const el = cursorSelector
        ? document.querySelector<HTMLElement>(cursorSelector)
        : null;

      if (shouldShowCursor && el && targetStep.navigateTo) {
        const rect = el.getBoundingClientRect();
        const targetX = rect.left + rect.width / 2;
        const targetY = rect.top + rect.height / 2;

        // Start cursor from center of viewport
        setCursorPos({
          x: window.innerWidth / 2,
          y: window.innerHeight / 2,
        });
        setShowCursor(true);
        setIsNavigating(true);

        // Animate cursor to element
        setTimeout(() => {
          setCursorPos({ x: targetX, y: targetY });

          // Click animation
          setTimeout(() => {
            setCursorClicking(true);

            // Navigate after click
            setTimeout(() => {
              setCurrentStep(stepIndex);
              expectedPathRef.current = targetStep.navigateTo!;
              router.push(targetStep.navigateTo!);
            }, 300);
          }, 600);
        }, 100);
      } else if (targetStep.navigateTo) {
        // No cursor animation, just navigate
        setIsNavigating(true);
        setCurrentStep(stepIndex);
        expectedPathRef.current = targetStep.navigateTo;
        router.push(targetStep.navigateTo);
      } else {
        // No navigation needed
        setCurrentStep(stepIndex);
      }
    },
    [
      step.showCursorAnimation,
      step.cursorTargetSelector,
      step.highlightSelector,
      router,
    ],
  );

  const goToStep = useCallback(
    (stepIndex: number) => {
      if (stepIndex < 0 || stepIndex >= steps.length) return;

      const targetStep = steps[stepIndex];
      setHighlightRect(null);

      if (targetStep.navigateTo && pathname !== targetStep.navigateTo) {
        animateCursorAndNavigate(targetStep, stepIndex);
      } else {
        setCurrentStep(stepIndex);
      }
    },
    [pathname, animateCursorAndNavigate],
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
      const prevStep = steps[currentStep - 1];
      setHighlightRect(null);
      setShowCursor(false);
      setCursorClicking(false);

      if (prevStep.navigateTo) {
        setIsNavigating(true);
        expectedPathRef.current = prevStep.navigateTo;
        setCurrentStep(currentStep - 1);
        router.push(prevStep.navigateTo);
      } else {
        setIsNavigating(true);
        expectedPathRef.current = "/dashboard";
        setCurrentStep(currentStep - 1);
        router.push("/dashboard");
      }
    }
  };

  const handleSkip = () => {
    completeOnboarding();
  };

  if (!isOpen) return null;

  const showHighlight = highlightRect && !isNavigating;

  // Create clip-path polygon for the dark overlay with a hole
  const getClipPath = () => {
    if (!highlightRect) return undefined;

    const padding = 8;
    const top = highlightRect.top - padding;
    const left = highlightRect.left - padding;
    const right = highlightRect.right + padding;
    const bottom = highlightRect.bottom + padding;

    return `polygon(
      0% 0%,
      0% 100%,
      ${left}px 100%,
      ${left}px ${top}px,
      ${right}px ${top}px,
      ${right}px ${bottom}px,
      ${left}px ${bottom}px,
      ${left}px 100%,
      100% 100%,
      100% 0%
    )`;
  };

  // Modal position - adjusted to be more centered vertically
  const getModalPosition = (): React.CSSProperties => {
    if (!showHighlight) {
      return {
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
      };
    }

    const modalWidth = 380;
    const modalHeight = 320;
    const gap = 24;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    // Try to position to the right
    let left = highlightRect!.right + gap;

    // If it goes off screen, position to the left
    if (left + modalWidth > viewportWidth - 20) {
      left = highlightRect!.left - modalWidth - gap;
    }

    // If still off screen, center below
    if (left < 20) {
      return {
        top: Math.min(
          highlightRect!.bottom + gap,
          viewportHeight - modalHeight - 20,
        ),
        left: "50%",
        transform: "translateX(-50%)",
      };
    }

    // Vertical centering - align with element but keep in viewport
    const elementCenterY = highlightRect!.top + highlightRect!.height / 2;
    let top = elementCenterY;

    // Ensure modal stays within viewport
    const minTop = modalHeight / 2 + 20;
    const maxTop = viewportHeight - modalHeight / 2 - 20;
    top = Math.max(minTop, Math.min(maxTop, top));

    return {
      top: top,
      left: left,
      transform: "translateY(-50%)",
    };
  };

  return (
    <div className="fixed inset-0 z-[9999]">
      {/* Dark overlay with cutout for highlighted element - hide when cursor is animating */}
      {!showCursor && (
        <div
          className="absolute inset-0 bg-black/75 transition-all duration-300"
          style={{
            clipPath: showHighlight ? getClipPath() : undefined,
            opacity: isNavigating ? 0.5 : 1,
          }}
        />
      )}

      {/* Glowing border around highlighted element */}
      {showHighlight && (
        <div
          className="absolute pointer-events-none z-[10000]"
          style={{
            top: highlightRect!.top - 8,
            left: highlightRect!.left - 8,
            width: highlightRect!.width + 16,
            height: highlightRect!.height + 16,
            borderRadius: 12,
            border: "3px solid white",
            boxShadow: `
              0 0 0 4px rgba(99, 102, 241, 0.9),
              0 0 20px 5px rgba(99, 102, 241, 0.7),
              0 0 40px 10px rgba(99, 102, 241, 0.5)
            `,
            animation: "onboarding-glow 2s ease-in-out infinite",
          }}
        />
      )}

      {/* Animated cursor */}
      {showCursor && (
        <div
          className="fixed pointer-events-none z-[10003] transition-all ease-out"
          style={{
            left: cursorPos.x,
            top: cursorPos.y,
            transform: `translate(-4px, -4px) scale(${cursorClicking ? 0.8 : 1})`,
            transitionDuration:
              cursorPos.x === window.innerWidth / 2 ? "0ms" : "600ms",
          }}
        >
          <MousePointer2
            className="w-8 h-8 text-white drop-shadow-lg"
            fill="white"
            strokeWidth={1.5}
            style={{
              filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.3))",
            }}
          />
          {cursorClicking && (
            <div className="absolute top-1 left-1 w-6 h-6 rounded-full bg-indigo-400/60 animate-ping" />
          )}
        </div>
      )}

      {/* Modal - always visible, buttons disabled during navigation */}
      <div
        className="fixed z-[10001] bg-white rounded-2xl shadow-2xl w-[380px] overflow-hidden transition-all duration-300"
        style={getModalPosition()}
      >
        {/* Arrow pointing to element */}
        {showHighlight && (
          <div
            className="absolute w-4 h-4 bg-white rotate-45 -left-2 top-1/2 -translate-y-1/2"
            style={{ boxShadow: "-2px 2px 8px rgba(0,0,0,0.15)" }}
          />
        )}

        {/* Gradient header */}
        <div className={`bg-gradient-to-r ${step.gradient} px-6 py-5 relative`}>
          <button
            onClick={handleSkip}
            className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-white/20 transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4 text-white/80" />
          </button>

          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Icon className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">{step.title}</h2>
              <p className="text-white/70 text-sm">
                Step {currentStep + 1} of {steps.length}
              </p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          <p className="text-gray-600 text-base leading-relaxed mb-6">
            {step.description}
          </p>

          {/* Progress bar */}
          <div className="flex gap-1.5 mb-6">
            {steps.map((_, i) => (
              <div
                key={i}
                className={`h-1.5 flex-1 rounded-full transition-all duration-300 ${
                  i <= currentStep ? "bg-indigo-500" : "bg-gray-200"
                }`}
              />
            ))}
          </div>

          {/* Buttons */}
          <div className="flex gap-3">
            {!isFirstStep && (
              <Button
                variant="outline"
                onClick={handleBack}
                disabled={isNavigating}
                className="gap-1.5"
              >
                <ChevronLeft className="w-4 h-4" />
                Back
              </Button>
            )}

            <Button
              onClick={handleNext}
              disabled={isNavigating}
              className={`flex-1 gap-2 bg-gradient-to-r ${step.gradient} hover:opacity-90 border-0 text-white`}
            >
              {isNavigating ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Loading...
                </>
              ) : isFirstStep ? (
                "Start Tour"
              ) : isLastStep ? (
                "Get Started"
              ) : (
                "Next"
              )}
              {!isNavigating && <ArrowRight className="w-4 h-4" />}
            </Button>
          </div>

          {!isLastStep && (
            <button
              onClick={handleSkip}
              disabled={isNavigating}
              className="w-full mt-4 text-sm text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-50"
            >
              Skip tour
            </button>
          )}
        </div>
      </div>

      {/* Animation styles */}
      <style jsx global>{`
        @keyframes onboarding-glow {
          0%,
          100% {
            box-shadow:
              0 0 0 4px rgba(99, 102, 241, 0.9),
              0 0 20px 5px rgba(99, 102, 241, 0.7),
              0 0 40px 10px rgba(99, 102, 241, 0.5);
          }
          50% {
            box-shadow:
              0 0 0 6px rgba(99, 102, 241, 1),
              0 0 30px 10px rgba(99, 102, 241, 0.8),
              0 0 60px 20px rgba(99, 102, 241, 0.6);
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
    sessionStorage.removeItem(ONBOARDING_STEP_KEY);
    setShouldShowOnboarding(true);
    window.location.reload();
  }, []);

  return { shouldShowOnboarding, resetOnboarding };
}
