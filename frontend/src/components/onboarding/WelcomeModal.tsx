"use client";

import { useState, useEffect, useCallback, useRef } from "react";
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
    secondarySelector: "mind-map-button",
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
    secondarySelector: "integrations-tab",
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

export function WelcomeModal({ onComplete }: WelcomeModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [highlightRect, setHighlightRect] = useState<DOMRect | null>(null);
  const [isAnimating, setIsAnimating] = useState(false);
  const [showCursor, setShowCursor] = useState(false);
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });
  const [cursorClicking, setCursorClicking] = useState(false);
  const [contentVisible, setContentVisible] = useState(true);
  const router = useRouter();
  const pathname = usePathname();
  const navigationPendingRef = useRef(false);

  const step = steps[currentStep];

  // Find element to highlight
  const findElement = useCallback((selector: string): Element | null => {
    // Direct selector
    const direct = document.querySelector(selector);
    if (direct) return direct;

    // Fallback for Mind Map button
    if (selector === "mind-map-button") {
      const buttons = document.querySelectorAll("button");
      for (let i = 0; i < buttons.length; i++) {
        if (buttons[i].textContent?.includes("Mind Map")) {
          return buttons[i];
        }
      }
    }

    // Fallback for Integrations tab
    if (selector === "integrations-tab") {
      const buttons = document.querySelectorAll("button");
      for (let i = 0; i < buttons.length; i++) {
        if (buttons[i].textContent?.includes("Integrations")) {
          return buttons[i];
        }
      }
    }

    return null;
  }, []);

  // Update highlight position
  const updateHighlight = useCallback(() => {
    if (!step.highlightSelector && !step.secondarySelector) {
      setHighlightRect(null);
      return;
    }

    // If we navigated and have a secondary selector, use that
    if (
      step.requiresNavigation &&
      step.navigationPath === pathname &&
      step.secondarySelector
    ) {
      const element = findElement(step.secondarySelector);
      if (element) {
        setHighlightRect(element.getBoundingClientRect());
        return;
      }
    }

    // Otherwise use primary selector
    if (step.highlightSelector) {
      const element = findElement(step.highlightSelector);
      if (element) {
        setHighlightRect(element.getBoundingClientRect());
        return;
      }
    }

    setHighlightRect(null);
  }, [step, pathname, findElement]);

  // Check if onboarding should show
  useEffect(() => {
    if (typeof window !== "undefined") {
      const completed = localStorage.getItem(ONBOARDING_KEY);
      if (!completed) {
        setTimeout(() => setIsOpen(true), 500);
      }
    }
  }, []);

  // Update highlight when step or path changes
  useEffect(() => {
    if (isOpen && !isAnimating) {
      // Small delay to let DOM settle after navigation
      const timer = setTimeout(updateHighlight, 100);
      return () => clearTimeout(timer);
    }
  }, [isOpen, currentStep, pathname, isAnimating, updateHighlight]);

  // Handle resize
  useEffect(() => {
    if (isOpen) {
      window.addEventListener("resize", updateHighlight);
      return () => window.removeEventListener("resize", updateHighlight);
    }
  }, [isOpen, updateHighlight]);

  // Handle navigation completion
  useEffect(() => {
    if (navigationPendingRef.current && step.navigationPath === pathname) {
      navigationPendingRef.current = false;
      // Navigation complete, show the secondary element
      setTimeout(() => {
        setIsAnimating(false);
        setShowCursor(false);
        setContentVisible(true);
        updateHighlight();
      }, 300);
    }
  }, [pathname, step.navigationPath, updateHighlight]);

  const handleComplete = useCallback(() => {
    localStorage.setItem(ONBOARDING_KEY, "true");
    setIsOpen(false);
    router.push("/dashboard");
    onComplete?.();
  }, [router, onComplete]);

  const animateCursorAndNavigate = useCallback(() => {
    if (!step.highlightSelector) return;

    const element = findElement(step.highlightSelector);
    if (!element) return;

    const rect = element.getBoundingClientRect();
    const targetX = rect.left + rect.width / 2;
    const targetY = rect.top + rect.height / 2;

    // Start cursor from center of screen
    setCursorPos({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
    setShowCursor(true);
    setContentVisible(false);

    // Animate to target
    setTimeout(() => {
      setCursorPos({ x: targetX, y: targetY });
    }, 100);

    // Click animation
    setTimeout(() => {
      setCursorClicking(true);
    }, 700);

    // Navigate
    setTimeout(() => {
      setCursorClicking(false);
      navigationPendingRef.current = true;
      if (step.navigationPath) {
        router.push(step.navigationPath);
      }
    }, 900);
  }, [step, findElement, router]);

  const handleNext = useCallback(() => {
    if (currentStep >= steps.length - 1) {
      handleComplete();
      return;
    }

    const nextStep = steps[currentStep + 1];

    // Fade out content
    setContentVisible(false);

    setTimeout(() => {
      setCurrentStep(currentStep + 1);

      if (nextStep.requiresNavigation) {
        setIsAnimating(true);
        // Start cursor animation after step updates
        setTimeout(() => {
          animateCursorAndNavigate();
        }, 50);
      } else {
        setContentVisible(true);
      }
    }, 200);
  }, [currentStep, handleComplete, animateCursorAndNavigate]);

  const handleBack = useCallback(() => {
    setContentVisible(false);
    setTimeout(() => {
      setCurrentStep(currentStep - 1);
      setContentVisible(true);
      router.push("/dashboard");
    }, 200);
  }, [currentStep, router]);

  const handleSkip = useCallback(() => {
    handleComplete();
  }, [handleComplete]);

  if (!isOpen) return null;

  const isLastStep = currentStep === steps.length - 1;
  const isFirstStep = currentStep === 0;
  const isCentered = step.position === "center" || !highlightRect;
  const Icon = step.icon;

  return (
    <div className="fixed inset-0 z-[9999]">
      {/* Dark overlay */}
      <div className="absolute inset-0 bg-black/75 transition-opacity duration-300" />

      {/* Highlight cutout */}
      {highlightRect && !isAnimating && (
        <div
          className="absolute pointer-events-none transition-all duration-500 ease-out"
          style={{
            top: highlightRect.top - 6,
            left: highlightRect.left - 6,
            width: highlightRect.width + 12,
            height: highlightRect.height + 12,
            borderRadius: 10,
            border: "2px solid #818cf8",
            boxShadow: `
              0 0 0 4000px rgba(0, 0, 0, 0.75),
              0 0 0 2px #6366f1,
              0 0 15px 5px rgba(99, 102, 241, 0.4)
            `,
          }}
        />
      )}

      {/* Animated cursor */}
      {showCursor && (
        <div
          className="fixed pointer-events-none z-[10000]"
          style={{
            left: cursorPos.x,
            top: cursorPos.y,
            transform: `translate(-50%, -50%) scale(${cursorClicking ? 0.8 : 1})`,
            transition:
              "left 0.5s ease-out, top 0.5s ease-out, transform 0.1s ease-out",
          }}
        >
          <MousePointer2
            className="w-8 h-8 text-white"
            fill="white"
            style={{ filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.5))" }}
          />
          {cursorClicking && (
            <div className="absolute top-0 left-0 w-8 h-8 rounded-full bg-indigo-400/40 animate-ping" />
          )}
        </div>
      )}

      {/* Modal */}
      <div
        className="fixed z-[10001] bg-white rounded-2xl shadow-2xl w-[340px] transition-all duration-300"
        style={{
          ...(isCentered
            ? {
                top: "50%",
                left: "50%",
                transform: `translate(-50%, -50%) scale(${contentVisible ? 1 : 0.95})`,
              }
            : highlightRect
              ? {
                  top: highlightRect.top + highlightRect.height / 2,
                  left: highlightRect.right + 24,
                  transform: `translateY(-50%) scale(${contentVisible ? 1 : 0.95})`,
                }
              : {
                  top: "50%",
                  left: "50%",
                  transform: `translate(-50%, -50%) scale(${contentVisible ? 1 : 0.95})`,
                }),
          opacity: contentVisible ? 1 : 0,
        }}
      >
        {/* Arrow */}
        {!isCentered && highlightRect && (
          <div
            className="absolute w-3 h-3 bg-white rotate-45 -left-1.5 top-1/2 -translate-y-1/2"
            style={{ boxShadow: "-1px 1px 2px rgba(0,0,0,0.1)" }}
          />
        )}

        {/* Close button */}
        <button
          onClick={handleSkip}
          className="absolute top-3 right-3 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <X className="w-4 h-4 text-gray-400" />
        </button>

        {/* Content */}
        <div className="p-5 text-center">
          <div
            className={`w-11 h-11 ${step.color} rounded-xl flex items-center justify-center mx-auto mb-3 shadow-md`}
          >
            <Icon className="w-5 h-5 text-white" />
          </div>

          <h2 className="text-base font-semibold text-gray-900 mb-1.5">
            {step.title}
          </h2>

          <p className="text-gray-500 text-sm leading-relaxed mb-4">
            {step.description}
          </p>

          {/* Progress dots */}
          <div className="flex items-center justify-center gap-1.5 mb-4">
            {steps.map((_, index) => (
              <div
                key={index}
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  index === currentStep
                    ? "w-5 bg-indigo-500"
                    : index < currentStep
                      ? "w-1.5 bg-indigo-300"
                      : "w-1.5 bg-gray-200"
                }`}
              />
            ))}
          </div>

          {/* Buttons */}
          <div className="flex gap-2">
            {currentStep > 0 && !isAnimating && (
              <Button
                variant="outline"
                onClick={handleBack}
                className="flex-1 h-9 text-sm rounded-lg"
                size="sm"
              >
                Back
              </Button>
            )}

            {isAnimating ? (
              <div className="flex-1 flex items-center justify-center h-9 text-sm text-gray-400">
                <div className="w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin mr-2" />
              </div>
            ) : isLastStep ? (
              <Button
                onClick={() => {
                  handleComplete();
                  router.push("/decisions/new");
                }}
                className="flex-1 h-9 text-sm rounded-lg bg-indigo-500 hover:bg-indigo-600"
                size="sm"
              >
                Get Started
                <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            ) : (
              <Button
                onClick={handleNext}
                className="flex-1 h-9 text-sm rounded-lg"
                size="sm"
              >
                {isFirstStep ? "Take a Tour" : "Next"}
                <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            )}
          </div>

          {!isLastStep && !isAnimating && (
            <button
              onClick={handleSkip}
              className="mt-2.5 text-xs text-gray-400 hover:text-gray-500 transition-colors"
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
