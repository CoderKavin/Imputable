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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

const ONBOARDING_KEY = "imputable_onboarding_complete";

interface WelcomeModalProps {
  onComplete?: () => void;
}

interface TourStep {
  title: string;
  description: string;
  icon: React.ElementType;
  color: string;
  // Element selector to highlight (null for centered modal)
  highlightSelector?: string;
  // Position of tooltip relative to highlighted element
  position?: "top" | "bottom" | "left" | "right" | "center";
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
      "Click here to document engineering decisions with context, alternatives, and expected outcomes. Every change creates a new version - nothing is ever lost.",
    icon: FileText,
    color: "bg-emerald-500",
    highlightSelector: '[href="/decisions"]',
    position: "right",
  },
  {
    title: "Visualize Relationships",
    description:
      "Switch to Mind Map view to see how decisions connect. AI can automatically discover relationships between your decisions.",
    icon: GitBranch,
    color: "bg-purple-500",
    highlightSelector: '[href="/decisions"]',
    position: "right",
  },
  {
    title: "Works Best with Slack & Teams",
    description:
      "Connect Slack or Microsoft Teams in Settings to create decisions without leaving your workflow.",
    icon: MessageSquare,
    color: "bg-blue-500",
    highlightSelector: '[href="/settings"]',
    position: "right",
  },
  {
    title: "Audit Trail",
    description:
      "Every action is logged. View the complete history of all decisions and changes for compliance and accountability.",
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
  const router = useRouter();

  // Find and measure the highlighted element
  const updateHighlight = useCallback(() => {
    const step = steps[currentStep];
    if (step.highlightSelector) {
      const element = document.querySelector(step.highlightSelector);
      if (element) {
        const rect = element.getBoundingClientRect();
        setHighlightRect(rect);
        return;
      }
    }
    setHighlightRect(null);
  }, [currentStep]);

  useEffect(() => {
    // Check if onboarding is already complete
    if (typeof window !== "undefined") {
      const completed = localStorage.getItem(ONBOARDING_KEY);
      if (!completed) {
        // Small delay to prevent flash
        const timer = setTimeout(() => setIsOpen(true), 500);
        return () => clearTimeout(timer);
      }
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      updateHighlight();
      // Update on resize
      window.addEventListener("resize", updateHighlight);
      return () => window.removeEventListener("resize", updateHighlight);
    }
  }, [isOpen, currentStep, updateHighlight]);

  const handleComplete = () => {
    localStorage.setItem(ONBOARDING_KEY, "true");
    setIsOpen(false);
    onComplete?.();
  };

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
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

  if (!isOpen) return null;

  const step = steps[currentStep];
  const isLastStep = currentStep === steps.length - 1;
  const isFirstStep = currentStep === 0;
  const isCentered = step.position === "center" || !highlightRect;
  const Icon = step.icon;

  // Calculate tooltip position based on highlighted element
  const getTooltipStyle = (): React.CSSProperties => {
    if (isCentered || !highlightRect) {
      return {
        position: "fixed",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
      };
    }

    const padding = 16;
    const tooltipWidth = 380;

    // Position to the right of the sidebar element
    return {
      position: "fixed",
      top: highlightRect.top + highlightRect.height / 2,
      left: highlightRect.right + padding + 20,
      transform: "translateY(-50%)",
      maxWidth: tooltipWidth,
    };
  };

  return (
    <div className="fixed inset-0 z-[300]">
      {/* Backdrop with cutout for highlighted element */}
      {isCentered ? (
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      ) : (
        <>
          {/* Dark overlay with hole for highlighted element */}
          <div className="absolute inset-0 bg-black/60" />
          {highlightRect && (
            <>
              {/* Highlight ring around element */}
              <div
                className="absolute z-[301] rounded-2xl ring-4 ring-indigo-500 ring-offset-4 ring-offset-transparent bg-transparent pointer-events-none transition-all duration-300"
                style={{
                  top: highlightRect.top - 8,
                  left: highlightRect.left - 8,
                  width: highlightRect.width + 16,
                  height: highlightRect.height + 16,
                  boxShadow: "0 0 0 9999px rgba(0, 0, 0, 0.6)",
                }}
              />
              {/* Pulse animation */}
              <div
                className="absolute z-[300] rounded-2xl animate-ping bg-indigo-500/30 pointer-events-none"
                style={{
                  top: highlightRect.top - 8,
                  left: highlightRect.left - 8,
                  width: highlightRect.width + 16,
                  height: highlightRect.height + 16,
                }}
              />
            </>
          )}
        </>
      )}

      {/* Tooltip/Modal */}
      <div
        className="z-[302] bg-white rounded-3xl shadow-2xl overflow-hidden"
        style={getTooltipStyle()}
      >
        {/* Arrow pointing to element (only when not centered) */}
        {!isCentered && highlightRect && (
          <div
            className="absolute w-4 h-4 bg-white transform rotate-45 -left-2 top-1/2 -translate-y-1/2"
            style={{ boxShadow: "-2px 2px 4px rgba(0,0,0,0.1)" }}
          />
        )}

        {/* Skip button */}
        <button
          onClick={handleSkip}
          className="absolute top-4 right-4 p-2 rounded-lg hover:bg-gray-100 transition-colors z-10"
        >
          <X className="w-5 h-5 text-gray-400" />
        </button>

        {/* Content */}
        <div className={`p-6 ${isCentered ? "pt-10" : "pt-6"} text-center`}>
          {/* Icon */}
          <div
            className={`w-14 h-14 ${step.color} rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg`}
          >
            <Icon className="w-7 h-7 text-white" />
          </div>

          {/* Title */}
          <h2 className="text-xl font-bold text-gray-900 mb-2">{step.title}</h2>

          {/* Description */}
          <p className="text-gray-600 text-sm leading-relaxed mb-6">
            {step.description}
          </p>

          {/* Progress dots */}
          <div className="flex items-center justify-center gap-2 mb-6">
            {steps.map((_, index) => (
              <button
                key={index}
                onClick={() => setCurrentStep(index)}
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

          {/* Actions */}
          <div className="flex gap-3">
            {currentStep > 0 && (
              <Button
                variant="outline"
                onClick={() => setCurrentStep(currentStep - 1)}
                className="flex-1 rounded-xl"
                size="sm"
              >
                Back
              </Button>
            )}

            {isLastStep ? (
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

          {/* Skip text */}
          {!isLastStep && (
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

/**
 * Hook to check if onboarding should be shown
 */
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
