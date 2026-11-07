import React, { useEffect, useState, useRef } from "react";
import {
  ArrowRight,
  ArrowLeft,
  X,
  CheckCircle2,
  Lightbulb,
} from "lucide-react";
import { Button, Badge } from "../ui";
import { useTour } from "../../context/TourContext";
import "./OnboardingSurfaces.css";

export const GuidedTour: React.FC = () => {
  const {
    isTourActive,
    isTourPreparing,
    currentStepIndex,
    currentStep,
    steps,
    totalSteps,
    nextStep,
    prevStep,
    skipTour,
    finishTour,
    goToStep,
  } = useTour();

  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);

  // Keyboard navigation for tour
  useEffect(() => {
    if (!isTourActive) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const editing =
        target?.isContentEditable ||
        ["INPUT", "TEXTAREA", "SELECT"].includes(target?.tagName || "");
      if (e.key !== "Escape" && editing) return;
      if (e.key === "Escape") {
        e.preventDefault();
        skipTour();
      } else if (
        !isTourPreparing &&
        e.key === "ArrowRight" &&
        currentStepIndex < totalSteps - 1
      ) {
        e.preventDefault();
        nextStep();
      } else if (
        !isTourPreparing &&
        e.key === "ArrowLeft" &&
        currentStepIndex > 0
      ) {
        e.preventDefault();
        prevStep();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    isTourActive,
    isTourPreparing,
    currentStepIndex,
    totalSteps,
    nextStep,
    prevStep,
    skipTour,
  ]);

  // Update target element bounding rect whenever step changes
  useEffect(() => {
    if (!isTourActive || !currentStep.targetSelector) {
      setTargetRect(null);
      return;
    }

    let scrolled = false;
    const updateRect = () => {
      const el = document.querySelector(currentStep.targetSelector!);
      if (el) {
        const rect = el.getBoundingClientRect();
        setTargetRect((previous) =>
          previous &&
          previous.top === rect.top &&
          previous.left === rect.left &&
          previous.width === rect.width &&
          previous.height === rect.height
            ? previous
            : rect,
        );
        // Scroll target into view smoothly if not visible
        if (
          !scrolled &&
          (rect.top < 60 || rect.bottom > window.innerHeight - 80)
        ) {
          scrolled = true;
          el.scrollIntoView({
            behavior: window.matchMedia("(prefers-reduced-motion: reduce)")
              .matches
              ? "auto"
              : "smooth",
            block: rect.height > window.innerHeight - 140 ? "start" : "center",
          });
        }
      } else {
        setTargetRect(null);
      }
    };

    // Immediate check + short retry to allow route transitions to render
    updateRect();
    const timer = setTimeout(updateRect, 300);
    const observer = new MutationObserver(updateRect);
    observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("resize", updateRect);
    window.addEventListener("scroll", updateRect, true);

    return () => {
      clearTimeout(timer);
      observer.disconnect();
      window.removeEventListener("resize", updateRect);
      window.removeEventListener("scroll", updateRect, true);
    };
  }, [isTourActive, currentStep]);

  if (!isTourActive) return null;

  const isLastStep = currentStepIndex === totalSteps - 1;
  const isFirstStep = currentStepIndex === 0;
  const progressPercent = Math.round(
    ((currentStepIndex + 1) / totalSteps) * 100,
  );

  return (
    <div className="guided-tour-layer fixed inset-0 z-50 pointer-events-none select-none">
      {/* Spotlight leaves the target clear and dims only the surrounding screen. */}
      {targetRect && (
        <div
          className="tour-highlight absolute rounded-xl pointer-events-none"
          aria-hidden="true"
          style={{
            top: targetRect.top - 6,
            left: targetRect.left - 6,
            width: targetRect.width + 12,
            height: targetRect.height + 12,
          }}
        />
      )}

      {/* Floating Tour Guide Card - Positioned in the Bottom Right Viewport Dock */}
      <div className="tour-surface fixed bottom-5 right-5 sm:right-8 max-w-md w-[calc(100vw-2.5rem)] pointer-events-auto z-50">
        <div
          ref={cardRef}
          role="region"
          aria-label="Optional guided tour"
          className="bg-white dark:bg-slate-900 border border-indigo-200 dark:border-indigo-900/60 rounded-2xl shadow-2xl overflow-hidden backdrop-blur-xl animate-in fade-in slide-in-from-bottom-3 duration-200"
        >
          {/* Header Progress Bar */}
          <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800">
            <div
              className="h-full bg-indigo-600 transition-all duration-300 rounded-r"
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          <div className="p-4 sm:p-5 space-y-3.5">
            {/* Top Toolbar: Step Counter & Close */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge tone={currentStep.badgeTone || "info"} size="sm">
                  {currentStep.badge}
                </Badge>
                <span className="text-[11px] font-mono font-semibold text-slate-500 dark:text-slate-400">
                  Step {currentStep.step} of {currentStep.totalSteps}
                </span>
              </div>

              <button
                type="button"
                onClick={skipTour}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded-lg transition-colors cursor-pointer"
                title="Exit Tour (Esc)"
                aria-label="Exit tour"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Step Title & Summary */}
            <div>
              <h3 className="text-sm sm:text-base font-bold text-slate-900 dark:text-white leading-snug">
                {currentStep.title}
              </h3>
              <p
                className="text-xs text-slate-600 dark:text-slate-300 mt-1 leading-relaxed"
                aria-live="polite"
              >
                {currentStep.details}
              </p>
            </div>

            {!targetRect && (
              <p className="tour-missing">
                This section may still be loading or may be unavailable. You can
                continue to the next step.
              </p>
            )}

            {/* Operator Tip Callout */}
            {currentStep.tip && (
              <div className="p-2.5 rounded-lg bg-amber-50/70 dark:bg-amber-950/20 border border-amber-200/80 dark:border-amber-900/40 text-[11px] text-amber-900 dark:text-amber-200 flex items-start gap-2">
                <Lightbulb className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span className="leading-tight">{currentStep.tip}</span>
              </div>
            )}

            {/* Step Dots Navigation */}
            <div className="flex items-center justify-center gap-1.5 pt-1">
              {steps.map((s, idx) => (
                <button
                  key={s.step}
                  type="button"
                  onClick={() => goToStep(idx)}
                  disabled={isTourPreparing}
                  className={`w-2 h-2 rounded-full transition-all cursor-pointer ${
                    idx === currentStepIndex
                      ? "w-5 bg-indigo-600"
                      : idx < currentStepIndex
                        ? "bg-slate-300 dark:bg-slate-700 hover:bg-slate-400"
                        : "bg-slate-200 dark:bg-slate-800 hover:bg-slate-300"
                  }`}
                  title={`Go to Step ${s.step}: ${s.title}`}
                  aria-label={`Go to step ${s.step}: ${s.title}`}
                  aria-current={idx === currentStepIndex ? "step" : undefined}
                />
              ))}
            </div>

            {/* Footer Action Buttons */}
            <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800 text-xs">
              <button
                type="button"
                onClick={skipTour}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 font-medium cursor-pointer"
              >
                Exit Tour
              </button>

              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={prevStep}
                  disabled={isFirstStep || isTourPreparing}
                  leftIcon={<ArrowLeft className="w-3.5 h-3.5" />}
                >
                  Back
                </Button>

                <Button
                  variant="primary"
                  size="sm"
                  onClick={isLastStep ? finishTour : nextStep}
                  disabled={isTourPreparing}
                  rightIcon={
                    isLastStep ? (
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    ) : (
                      <ArrowRight className="w-3.5 h-3.5" />
                    )
                  }
                >
                  {isLastStep ? "Finish Tour" : "Next Step"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
