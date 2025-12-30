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

// State machine for animation phases
type AnimationPhase =
  | "idle" // Normal state, showing modal
  | "fading-out" // Fading out modal before cursor animation
  | "cursor-moving" // Cursor moving to target
  | "cursor-clicking" // Cursor click animation
  | "navigating" // Navigation in progress
  | "waiting-for-page" // Waiting for new page to load
  | "fading-in"; // Fading in modal after navigation

export function WelcomeModal({ onComplete }: WelcomeModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [highlightRect, setHighlightRect] = useState<DOMRect | null>(null);
  const [phase, setPhase] = useState<AnimationPhase>("idle");
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });
  const [hasNavigated, setHasNavigated] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const step = steps[currentStep];

  // Cleanup timeouts on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  // Find element to highlight
  const findElement = useCallback((selector: string): Element | null => {
    if (!selector) return null;

    // Direct CSS selector
    try {
      const direct = document.querySelector(selector);
      if (direct) return direct;
    } catch {
      // Invalid selector
    }

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
    // Determine which selector to use
    let selector: string | undefined;

    if (hasNavigated && step.secondarySelector) {
      selector = step.secondarySelector;
    } else if (step.highlightSelector) {
      selector = step.highlightSelector;
    }

    if (!selector) {
      setHighlightRect(null);
      return;
    }

    const element = findElement(selector);
    if (element) {
      setHighlightRect(element.getBoundingClientRect());
    } else {
      setHighlightRect(null);
    }
  }, [step, hasNavigated, findElement]);

  // Check if onboarding should show
  useEffect(() => {
    if (typeof window !== "undefined") {
      const completed = localStorage.getItem(ONBOARDING_KEY);
      if (!completed) {
        setTimeout(() => setIsOpen(true), 500);
      }
    }
  }, []);

  // Update highlight when relevant state changes
  useEffect(() => {
    if (isOpen && phase === "idle") {
      const timer = setTimeout(updateHighlight, 150);
      return () => clearTimeout(timer);
    }
  }, [isOpen, currentStep, phase, hasNavigated, updateHighlight]);

  // Handle resize
  useEffect(() => {
    if (isOpen && phase === "idle") {
      window.addEventListener("resize", updateHighlight);
      return () => window.removeEventListener("resize", updateHighlight);
    }
  }, [isOpen, phase, updateHighlight]);

  // Handle navigation completion - detect when we arrive at target page
  useEffect(() => {
    if (phase === "waiting-for-page" && step.navigationPath) {
      // Check if we're on the right page
      if (
        pathname === step.navigationPath ||
        pathname.startsWith(step.navigationPath)
      ) {
        // Wait for page to render, then show the secondary element
        timeoutRef.current = setTimeout(() => {
          setHasNavigated(true);
          setPhase("fading-in");
          // After fade in completes
          timeoutRef.current = setTimeout(() => {
            setPhase("idle");
            updateHighlight();
          }, 300);
        }, 500);
      }
    }
  }, [pathname, phase, step.navigationPath, updateHighlight]);

  const handleComplete = useCallback(() => {
    localStorage.setItem(ONBOARDING_KEY, "true");
    setIsOpen(false);
    router.push("/dashboard");
    onComplete?.();
  }, [router, onComplete]);

  const startCursorAnimation = useCallback(() => {
    const element = findElement(step.highlightSelector || "");

    if (!element) {
      // No element found - skip cursor animation, just navigate
      setPhase("navigating");
      if (step.navigationPath) {
        router.push(step.navigationPath);
        setPhase("waiting-for-page");
      } else {
        setPhase("idle");
        setHasNavigated(true);
      }
      return;
    }

    const rect = element.getBoundingClientRect();
    const targetX = rect.left + rect.width / 2;
    const targetY = rect.top + rect.height / 2;

    // Start cursor from center of screen
    setCursorPos({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
    setPhase("cursor-moving");

    // Move cursor to target
    timeoutRef.current = setTimeout(() => {
      setCursorPos({ x: targetX, y: targetY });

      // Click animation
      timeoutRef.current = setTimeout(() => {
        setPhase("cursor-clicking");

        // Navigate after click
        timeoutRef.current = setTimeout(() => {
          setPhase("navigating");

          if (step.navigationPath) {
            router.push(step.navigationPath);
            setPhase("waiting-for-page");
          } else {
            setPhase("idle");
            setHasNavigated(true);
          }
        }, 200);
      }, 500);
    }, 100);
  }, [step, findElement, router]);

  const handleNext = useCallback(() => {
    if (currentStep >= steps.length - 1) {
      handleComplete();
      return;
    }

    const nextStep = steps[currentStep + 1];

    // Start fade out
    setPhase("fading-out");
    setHighlightRect(null);

    timeoutRef.current = setTimeout(() => {
      setCurrentStep(currentStep + 1);
      setHasNavigated(false);

      if (nextStep.requiresNavigation) {
        // Start cursor animation for navigation steps
        startCursorAnimation();
      } else {
        // Simple step transition
        setPhase("fading-in");
        timeoutRef.current = setTimeout(() => {
          setPhase("idle");
        }, 200);
      }
    }, 200);
  }, [currentStep, handleComplete, startCursorAnimation]);

  const handleBack = useCallback(() => {
    setPhase("fading-out");
    setHighlightRect(null);

    timeoutRef.current = setTimeout(() => {
      setCurrentStep(currentStep - 1);
      setHasNavigated(false);
      router.push("/dashboard");

      setPhase("fading-in");
      timeoutRef.current = setTimeout(() => {
        setPhase("idle");
      }, 300);
    }, 200);
  }, [currentStep, router]);

  if (!isOpen) return null;

  const isLastStep = currentStep === steps.length - 1;
  const isFirstStep = currentStep === 0;
  const showModal =
    phase === "idle" || phase === "fading-out" || phase === "fading-in";
  const showCursor = phase === "cursor-moving" || phase === "cursor-clicking";
  const isAnimating = phase !== "idle";
  const modalVisible = phase === "idle" || phase === "fading-in";
  const isCentered = step.position === "center" || !highlightRect;
  const Icon = step.icon;

  return (
    <div className="fixed inset-0 z-[9999]">
      {/* Dark overlay - always visible */}
      <div
        className="absolute inset-0 bg-black/75 transition-opacity duration-300"
        style={{ opacity: showCursor ? 0.85 : 1 }}
      />

      {/* Highlight cutout */}
      {highlightRect && phase === "idle" && (
        <>
          {/* Border around highlighted element */}
          <div
            className="absolute pointer-events-none z-[10000] transition-all duration-300 ease-out"
            style={{
              top: highlightRect.top - 4,
              left: highlightRect.left - 4,
              width: highlightRect.width + 8,
              height: highlightRect.height + 8,
              borderRadius: 8,
              border: "2px solid #6366f1",
              boxShadow: "0 0 12px 2px rgba(99, 102, 241, 0.5)",
            }}
          />
          {/* Dark overlay with cutout */}
          <div
            className="absolute inset-0 pointer-events-none bg-black/75"
            style={{
              clipPath: `polygon(
                0% 0%, 0% 100%, 100% 100%, 100% 0%, 0% 0%,
                ${highlightRect.left - 4}px ${highlightRect.top - 4}px,
                ${highlightRect.left - 4}px ${highlightRect.top + highlightRect.height + 4}px,
                ${highlightRect.left + highlightRect.width + 4}px ${highlightRect.top + highlightRect.height + 4}px,
                ${highlightRect.left + highlightRect.width + 4}px ${highlightRect.top - 4}px,
                ${highlightRect.left - 4}px ${highlightRect.top - 4}px
              )`,
            }}
          />
        </>
      )}

      {/* Animated cursor */}
      {showCursor && (
        <div
          className="fixed pointer-events-none z-[10002]"
          style={{
            left: cursorPos.x,
            top: cursorPos.y,
            transform: `translate(-50%, -50%) scale(${phase === "cursor-clicking" ? 0.8 : 1})`,
            transition:
              "left 0.5s ease-out, top 0.5s ease-out, transform 0.15s ease-out",
          }}
        >
          <MousePointer2
            className="w-8 h-8 text-white"
            fill="white"
            style={{ filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.5))" }}
          />
          {phase === "cursor-clicking" && (
            <div className="absolute top-0 left-0 w-8 h-8 rounded-full bg-indigo-400/50 animate-ping" />
          )}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div
          className="fixed z-[10001] bg-white rounded-2xl shadow-2xl w-[340px] transition-all duration-200 ease-out"
          style={{
            ...(isCentered
              ? {
                  top: "50%",
                  left: "50%",
                  transform: `translate(-50%, -50%) scale(${modalVisible ? 1 : 0.95})`,
                }
              : highlightRect
                ? {
                    top: highlightRect.top + highlightRect.height / 2,
                    left: highlightRect.right + 24,
                    transform: `translateY(-50%) scale(${modalVisible ? 1 : 0.95})`,
                  }
                : {
                    top: "50%",
                    left: "50%",
                    transform: `translate(-50%, -50%) scale(${modalVisible ? 1 : 0.95})`,
                  }),
            opacity: modalVisible ? 1 : 0,
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
            onClick={handleComplete}
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

              {isLastStep ? (
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
                  disabled={isAnimating}
                  className="flex-1 h-9 text-sm rounded-lg"
                  size="sm"
                >
                  {isFirstStep ? "Take a Tour" : "Next"}
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              )}
            </div>

            {!isLastStep && (
              <button
                onClick={handleComplete}
                className="mt-2.5 text-xs text-gray-400 hover:text-gray-500 transition-colors"
              >
                Skip tour
              </button>
            )}
          </div>
        </div>
      )}

      {/* Loading state during navigation */}
      {(phase === "navigating" || phase === "waiting-for-page") && (
        <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[10001]">
          <div className="w-8 h-8 border-3 border-white border-t-transparent rounded-full animate-spin" />
        </div>
      )}
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
