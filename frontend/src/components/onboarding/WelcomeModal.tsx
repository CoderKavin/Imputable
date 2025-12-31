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
  navigateTo?: string;
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
      "Switch to Mind Map view to see how decisions connect. AI can automatically discover relationships!",
    icon: GitBranch,
    gradient: "from-purple-500 to-pink-600",
    highlightSelector: '[data-onboarding="mind-map-button"]',
    navigateTo: "/decisions",
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
    highlightSelector: '[href="/audit"]',
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
  const [currentStep, setCurrentStep] = useState(0);
  const [highlightRect, setHighlightRect] = useState<DOMRect | null>(null);
  const [isTransitioning, setIsTransitioning] = useState(false);

  const router = useRouter();
  const pathname = usePathname();
  const retryRef = useRef<NodeJS.Timeout | null>(null);

  const step = steps[currentStep];
  const isLastStep = currentStep === steps.length - 1;
  const isFirstStep = currentStep === 0;
  const hasHighlight = !!step.highlightSelector;
  const Icon = step.icon;

  // Find and highlight element with retries
  const findAndHighlight = useCallback(() => {
    if (!step.highlightSelector) {
      setHighlightRect(null);
      return;
    }

    const el = document.querySelector<HTMLElement>(step.highlightSelector);
    if (el) {
      const rect = el.getBoundingClientRect();
      setHighlightRect(rect);
      if (retryRef.current) {
        clearInterval(retryRef.current);
        retryRef.current = null;
      }
    } else {
      setHighlightRect(null);
    }
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

  // Update highlight when step changes or after navigation
  useEffect(() => {
    if (!isOpen || isTransitioning) return;

    // Clear any existing retry interval
    if (retryRef.current) {
      clearInterval(retryRef.current);
    }

    // Try immediately
    findAndHighlight();

    // Keep retrying for elements that might not be rendered yet
    let attempts = 0;
    retryRef.current = setInterval(() => {
      attempts++;
      findAndHighlight();
      if (attempts > 20) {
        // Stop after ~2 seconds
        if (retryRef.current) {
          clearInterval(retryRef.current);
          retryRef.current = null;
        }
      }
    }, 100);

    // Handle resize/scroll
    const handleUpdate = () => findAndHighlight();
    window.addEventListener("resize", handleUpdate);
    window.addEventListener("scroll", handleUpdate);

    return () => {
      if (retryRef.current) {
        clearInterval(retryRef.current);
        retryRef.current = null;
      }
      window.removeEventListener("resize", handleUpdate);
      window.removeEventListener("scroll", handleUpdate);
    };
  }, [isOpen, currentStep, isTransitioning, findAndHighlight, pathname]);

  const completeOnboarding = useCallback(() => {
    localStorage.setItem(ONBOARDING_KEY, "true");
    setIsOpen(false);
  }, []);

  const goToStep = useCallback(
    (stepIndex: number) => {
      if (stepIndex < 0 || stepIndex >= steps.length) return;

      const targetStep = steps[stepIndex];

      setIsTransitioning(true);
      setHighlightRect(null);

      // Navigate if needed
      if (targetStep.navigateTo && pathname !== targetStep.navigateTo) {
        router.push(targetStep.navigateTo);
      }

      // Wait for transition, then update step
      setTimeout(() => {
        setCurrentStep(stepIndex);
        setIsTransitioning(false);
      }, 300);
    },
    [pathname, router],
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
      goToStep(currentStep - 1);
    }
  };

  const handleSkip = () => {
    completeOnboarding();
    router.push("/dashboard");
  };

  if (!isOpen) return null;

  // Modal position - centered if no highlight, otherwise to the side
  const getModalPosition = (): React.CSSProperties => {
    if (!hasHighlight || !highlightRect) {
      return {
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
      };
    }

    const modalWidth = 380;
    const gap = 24;
    const viewportWidth =
      typeof window !== "undefined" ? window.innerWidth : 1200;

    // Try to position to the right
    let left = highlightRect.right + gap;

    // If it goes off screen, position to the left
    if (left + modalWidth > viewportWidth - 20) {
      left = highlightRect.left - modalWidth - gap;
    }

    // If still off screen, center it
    if (left < 20) {
      return {
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
      };
    }

    return {
      top: Math.max(20, highlightRect.top + highlightRect.height / 2),
      left: left,
      transform: "translateY(-50%)",
    };
  };

  return (
    <div className="fixed inset-0 z-[9999]">
      {/* Dark overlay */}
      <div
        className="absolute inset-0 bg-black/70 transition-opacity duration-300"
        style={{ opacity: isTransitioning ? 0.5 : 1 }}
      />

      {/* Spotlight cutout - creates a hole in the overlay */}
      {highlightRect && !isTransitioning && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: `radial-gradient(
              ellipse ${Math.max(highlightRect.width, highlightRect.height) + 100}px ${Math.max(highlightRect.width, highlightRect.height) + 100}px
              at ${highlightRect.left + highlightRect.width / 2}px ${highlightRect.top + highlightRect.height / 2}px,
              transparent 0%,
              transparent 40%,
              rgba(0, 0, 0, 0.7) 100%
            )`,
          }}
        />
      )}

      {/* Highlight border with glow */}
      {highlightRect && !isTransitioning && (
        <div
          className="absolute pointer-events-none z-[10000]"
          style={{
            top: highlightRect.top - 8,
            left: highlightRect.left - 8,
            width: highlightRect.width + 16,
            height: highlightRect.height + 16,
            borderRadius: 16,
            border: "3px solid white",
            boxShadow: `
              0 0 0 3px rgba(99, 102, 241, 0.8),
              0 0 30px 10px rgba(99, 102, 241, 0.6),
              0 0 60px 20px rgba(99, 102, 241, 0.4),
              inset 0 0 30px rgba(255, 255, 255, 0.2)
            `,
            animation: "onboarding-pulse 2s ease-in-out infinite",
          }}
        />
      )}

      {/* Modal */}
      <div
        className={`fixed z-[10001] bg-white rounded-2xl shadow-2xl w-[380px] overflow-hidden transition-all duration-300 ${
          isTransitioning ? "opacity-0 scale-95" : "opacity-100 scale-100"
        }`}
        style={getModalPosition()}
      >
        {/* Arrow pointing to element */}
        {hasHighlight && highlightRect && !isTransitioning && (
          <div
            className="absolute w-4 h-4 bg-white rotate-45 -left-2 top-1/2 -translate-y-1/2 shadow-lg"
            style={{ boxShadow: "-2px 2px 5px rgba(0,0,0,0.1)" }}
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

          {/* Progress dots */}
          <div className="flex justify-center gap-2 mb-6">
            {steps.map((_, i) => (
              <div
                key={i}
                className={`h-2 rounded-full transition-all duration-300 ${
                  i === currentStep
                    ? "w-6 bg-indigo-500"
                    : i < currentStep
                      ? "w-2 bg-indigo-300"
                      : "w-2 bg-gray-200"
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
                className="gap-1.5"
                disabled={isTransitioning}
              >
                <ChevronLeft className="w-4 h-4" />
                Back
              </Button>
            )}

            <Button
              onClick={handleNext}
              className={`flex-1 gap-2 bg-gradient-to-r ${step.gradient} hover:opacity-90 border-0 text-white`}
              disabled={isTransitioning}
            >
              {isFirstStep ? "Start Tour" : isLastStep ? "Get Started" : "Next"}
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>

          {!isLastStep && (
            <button
              onClick={handleSkip}
              className="w-full mt-4 text-sm text-gray-400 hover:text-gray-600 transition-colors"
            >
              Skip tour
            </button>
          )}
        </div>
      </div>

      {/* Global styles for animation */}
      <style jsx global>{`
        @keyframes onboarding-pulse {
          0%,
          100% {
            box-shadow:
              0 0 0 3px rgba(99, 102, 241, 0.8),
              0 0 30px 10px rgba(99, 102, 241, 0.6),
              0 0 60px 20px rgba(99, 102, 241, 0.4),
              inset 0 0 30px rgba(255, 255, 255, 0.2);
          }
          50% {
            box-shadow:
              0 0 0 5px rgba(99, 102, 241, 1),
              0 0 40px 15px rgba(99, 102, 241, 0.7),
              0 0 80px 30px rgba(99, 102, 241, 0.5),
              inset 0 0 40px rgba(255, 255, 255, 0.3);
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
