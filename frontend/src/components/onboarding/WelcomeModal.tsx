"use client";

import { useState, useEffect } from "react";
import { X, FileText, GitBranch, Shield, Bell, ArrowRight, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

const ONBOARDING_KEY = "imputable_onboarding_complete";

interface WelcomeModalProps {
  onComplete?: () => void;
}

const steps = [
  {
    title: "Welcome to Imputable",
    description: "The decision tracking platform that helps engineering teams document, track, and audit their key decisions.",
    icon: Sparkles,
    color: "bg-indigo-500",
  },
  {
    title: "Create Decisions",
    description: "Document engineering decisions with context, alternatives considered, and expected outcomes. Every change creates a new version - nothing is ever lost.",
    icon: FileText,
    color: "bg-emerald-500",
  },
  {
    title: "Visualize Relationships",
    description: "Use the Mind Map view to see how decisions connect. AI can automatically discover relationships between your decisions.",
    icon: GitBranch,
    color: "bg-purple-500",
  },
  {
    title: "Review & Approve",
    description: "Set up approval workflows for important decisions. Track who approved what and when with full audit trails.",
    icon: Shield,
    color: "bg-amber-500",
  },
  {
    title: "Risk Monitoring",
    description: "Get alerted when decisions may need review. The risk dashboard helps you stay on top of decisions that might be impacted by changes.",
    icon: Bell,
    color: "bg-rose-500",
  },
];

export function WelcomeModal({ onComplete }: WelcomeModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const router = useRouter();

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
  const Icon = step.icon;

  return (
    <div className="fixed inset-0 z-[300] flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Modal */}
      <div className="relative z-[301] bg-white rounded-3xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        {/* Skip button */}
        <button
          onClick={handleSkip}
          className="absolute top-4 right-4 p-2 rounded-lg hover:bg-gray-100 transition-colors z-10"
        >
          <X className="w-5 h-5 text-gray-400" />
        </button>

        {/* Content */}
        <div className="p-8 pt-12 text-center">
          {/* Icon */}
          <div className={`w-16 h-16 ${step.color} rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg`}>
            <Icon className="w-8 h-8 text-white" />
          </div>

          {/* Title */}
          <h2 className="text-2xl font-bold text-gray-900 mb-3">
            {step.title}
          </h2>

          {/* Description */}
          <p className="text-gray-600 leading-relaxed mb-8">
            {step.description}
          </p>

          {/* Progress dots */}
          <div className="flex items-center justify-center gap-2 mb-8">
            {steps.map((_, index) => (
              <button
                key={index}
                onClick={() => setCurrentStep(index)}
                className={`
                  w-2 h-2 rounded-full transition-all duration-300
                  ${index === currentStep
                    ? "w-8 bg-indigo-500"
                    : index < currentStep
                      ? "bg-indigo-300"
                      : "bg-gray-200"
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
              >
                Back
              </Button>
            )}

            {isLastStep ? (
              <Button
                onClick={handleGetStarted}
                className="flex-1 rounded-xl bg-indigo-500 hover:bg-indigo-600"
              >
                Create Your First Decision
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            ) : (
              <Button
                onClick={handleNext}
                className="flex-1 rounded-xl"
              >
                Next
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            )}
          </div>

          {/* Skip text */}
          {!isLastStep && (
            <button
              onClick={handleSkip}
              className="mt-4 text-sm text-gray-400 hover:text-gray-600 transition-colors"
            >
              Skip intro
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
