import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
} from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { api } from "../api/client";
import type { AuthenticatedUser } from "../types";
import { onboardingStorageKey } from "../utils/onboardingStorage";

export interface TourStep {
  step: number;
  totalSteps: number;
  route: string;
  targetSelector?: string;
  title: string;
  summary: string;
  details: string;
  badge: string;
  badgeTone?: "neutral" | "success" | "warning" | "error" | "info" | "purple";
  tip?: string;
}

const BASE_STEPS: Omit<TourStep, "step" | "totalSteps">[] = [
  {
    route: "/today",
    targetSelector: '[data-tour="today-kpi-bar"]',
    title: "Today",
    summary: "Start with the current workload.",
    details:
      "See invoices received, intake jobs, open issue records and completed internal sign-offs. These figures describe different datasets. Below, open an invoice for evidence or browse recent audit events.",
    badge: "Overview",
  },
  {
    route: "/invoices",
    targetSelector: '[data-tour="inbox-queue-tabs"]',
    title: "Invoice inbox",
    summary: "Find invoices by queue.",
    details:
      "Use the existing queue tabs, period filters and search. Open an invoice to review its evidence.",
    badge: "Invoices",
  },
  {
    route: "/invoices/:available",
    targetSelector: '[data-tour="policy-gates-trigger"]',
    title: "Review an invoice",
    summary: "Inspect available evidence.",
    details:
      "This is an existing invoice in your workspace, not a protected practice copy. Inspect the document, checks and variances. The tour does not submit decisions.",
    badge: "Review",
  },
  {
    route: "/exceptions",
    targetSelector: '[data-tour="exceptions-table"]',
    title: "Exceptions",
    summary: "Investigate issues.",
    details:
      "An exception is an issue record, not an invoice count. Review its recorded exposure and owner; authorized roles can reassign it. Open the invoice to investigate.",
    badge: "Exceptions",
  },
  {
    route: "/approvals",
    targetSelector: '[data-tour="approvals-table"]',
    title: "Approvals",
    summary: "Understand independent sign-off.",
    details:
      "Review eligibility and any blocking reason. Internal sign-off does not make a bank payment.",
    badge: "Approvals",
  },
  {
    route: "/audit",
    targetSelector: '[data-tour="audit-table"]',
    title: "Audit trail",
    summary: "Trace recorded activity.",
    details:
      "Search the latest requested events and open Details for available reasons, references and state changes. This view requests up to 100 events.",
    badge: "Audit",
  },
  {
    route: "/settings/connections",
    targetSelector: '[data-tour="connections"]',
    title: "Connections",
    summary: "Check service status.",
    details:
      "See available integration status and actions. A snapshot or configured service does not necessarily mean live synchronization.",
    badge: "Connections",
  },
  {
    route: "/settings/reference-data",
    targetSelector: '[data-tour="reference-records"]',
    title: "Procurement records",
    summary: "Inspect reference data.",
    details:
      "Review the source and provenance of the supplier, order, receipt and inspection records used for matching.",
    badge: "Records",
  },
  {
    route: "/settings/team",
    targetSelector: '[data-tour="team-access"]',
    title: "Team and access",
    summary: "Review access.",
    details:
      "Available team and access actions depend on your role. No access changes are made during this tour.",
    badge: "Team",
  },
  {
    route: "/setup",
    targetSelector: '[data-tour="setup"]',
    title: "Setup guide",
    summary: "Return to setup anytime.",
    details:
      "Work through the optional setup steps at your own pace. The contextual help menu can restart this tour.",
    badge: "Setup",
  },
];

interface TourContextType {
  // Welcome Modal
  isWelcomeOpen: boolean;
  openWelcome: () => void;
  closeWelcome: () => void;
  dismissWelcomeForever: () => void;

  // Interactive Tour
  isTourActive: boolean;
  isTourPreparing: boolean;
  currentStepIndex: number;
  currentStep: TourStep;
  steps: TourStep[];
  totalSteps: number;
  startTour: (fromStep?: number) => void;
  nextStep: () => void;
  prevStep: () => void;
  goToStep: (stepIndex: number) => void;
  skipTour: () => void;
  finishTour: () => void;
  restartTour: () => void;

  // Contextual Help Drawer
  isHelpOpen: boolean;
  openHelp: (tab?: "screen" | "overview" | "glossary" | "faq") => void;
  closeHelp: () => void;
  activeHelpTab: "screen" | "overview" | "glossary" | "faq";
  setActiveHelpTab: (tab: "screen" | "overview" | "glossary" | "faq") => void;
}

const TourContext = createContext<TourContextType | undefined>(undefined);

export const TourProvider: React.FC<{
  children: React.ReactNode;
  currentUser: AuthenticatedUser;
}> = ({ children, currentUser }) => {
  const lookupSequence = useRef(0);
  // Invalidate outstanding lookups on account change or unmount.
  useEffect(
    () => () => {
      lookupSequence.current += 1;
    },
    [currentUser.id, currentUser.org_id],
  );

  const makeSteps = useCallback(
    (
      invoiceId: string | null,
      status: "loading" | "available" | "empty" | "error",
    ): TourStep[] =>
      BASE_STEPS.filter((step) => {
        if (step.route === "/invoices/:available") return Boolean(invoiceId);
        if (step.route === "/approvals") return currentUser.role !== "AUDITOR";
        if (step.route === "/settings/team")
          return ["AP_LEAD", "CONTROLLER", "SYSTEM_ADMIN"].includes(
            currentUser.role || "",
          );
        return true;
      }).map((step, index, all) => ({
        ...step,
        details:
          step.route === "/today" && status !== "available"
            ? `${step.details} ${status === "empty" ? "No invoice was found on the first inbox page, so the review step is omitted." : status === "error" ? "The inbox could not be checked, so the review step is omitted. Restart the tour to retry." : "Checking for an invoice before the tour continues."}`
            : step.details,
        route:
          step.route === "/invoices/:available"
            ? `/invoices/${invoiceId}`
            : step.route,
        step: index + 1,
        totalSteps: all.length,
      })),
    [currentUser.role],
  );
  const navigate = useNavigate();
  const location = useLocation();

  // Welcome modal state
  const [isWelcomeOpen, setIsWelcomeOpen] = useState<boolean>(false);

  // Tour state
  const [isTourActive, setIsTourActive] = useState<boolean>(false);
  const [isTourPreparing, setIsTourPreparing] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [tourSteps, setTourSteps] = useState<TourStep[]>([]);
  const steps = isTourActive ? tourSteps : makeSteps(null, "loading");

  // Help drawer state
  const [isHelpOpen, setIsHelpOpen] = useState<boolean>(false);
  const [activeHelpTab, setActiveHelpTab] = useState<
    "screen" | "overview" | "glossary" | "faq"
  >("screen");

  // Check initial visit on mount
  useEffect(() => {
    try {
      const welcomeDismissed = localStorage.getItem(
        onboardingStorageKey(
          currentUser.id,
          currentUser.org_id || "",
          "welcome_dismissed",
        ),
      );
      const tourCompleted = localStorage.getItem(
        onboardingStorageKey(
          currentUser.id,
          currentUser.org_id || "",
          "tour_completed",
        ),
      );
      if (!welcomeDismissed && !tourCompleted) {
        // Small delay so the page loads cleanly first
        const timer = setTimeout(() => {
          setIsWelcomeOpen(true);
        }, 600);
        return () => clearTimeout(timer);
      }
    } catch {
      // Ignore localStorage restrictions
    }
  }, [currentUser.id, currentUser.org_id]);

  const openWelcome = useCallback(() => setIsWelcomeOpen(true), []);
  const closeWelcome = useCallback(() => setIsWelcomeOpen(false), []);
  const dismissWelcomeForever = useCallback(() => {
    setIsWelcomeOpen(false);
    try {
      localStorage.setItem(
        onboardingStorageKey(
          currentUser.id,
          currentUser.org_id || "",
          "welcome_dismissed",
        ),
        "true",
      );
    } catch {
      // Ignore
    }
  }, [currentUser.id, currentUser.org_id]);

  const currentStep = steps[currentStepIndex] || steps[0];
  const totalSteps = steps.length;

  const startTour = useCallback(
    (fromStep: number = 0) => {
      const request = ++lookupSequence.current;
      const preparingSteps = makeSteps(null, "loading");
      setIsWelcomeOpen(false);
      setIsHelpOpen(false);
      setCurrentStepIndex(0);
      setTourSteps(preparingSteps);
      setIsTourPreparing(true);
      setIsTourActive(true);
      if (location.pathname !== preparingSteps[0].route)
        navigate(preparingSteps[0].route);

      api
        .getInbox({ page: 1 })
        .then((res) => {
          if (res.message || !Array.isArray(res.items))
            throw new Error("Inbox unavailable");
          const id = res.items?.[0]?.id || null;
          return makeSteps(id, id ? "available" : "empty");
        })
        .catch(() => makeSteps(null, "error"))
        .then((resolvedSteps) => {
          if (request !== lookupSequence.current) return;
          const index = Math.max(
            0,
            Math.min(fromStep, resolvedSteps.length - 1),
          );
          setTourSteps(resolvedSteps);
          setCurrentStepIndex(index);
          setIsTourPreparing(false);
          if (index !== 0) navigate(resolvedSteps[index].route);
        });
    },
    [location.pathname, navigate, makeSteps],
  );

  const finishTour = useCallback(() => {
    lookupSequence.current += 1;
    setIsTourPreparing(false);
    setIsTourActive(false);
    try {
      localStorage.setItem(
        onboardingStorageKey(
          currentUser.id,
          currentUser.org_id || "",
          "tour_completed",
        ),
        "true",
      );
      localStorage.setItem(
        onboardingStorageKey(
          currentUser.id,
          currentUser.org_id || "",
          "welcome_dismissed",
        ),
        "true",
      );
    } catch {
      // Ignore
    }
  }, [currentUser.id, currentUser.org_id]);

  const skipTour = useCallback(() => {
    lookupSequence.current += 1;
    setIsTourPreparing(false);
    setIsTourActive(false);
    try {
      localStorage.setItem(
        onboardingStorageKey(
          currentUser.id,
          currentUser.org_id || "",
          "tour_completed",
        ),
        "true",
      );
      localStorage.setItem(
        onboardingStorageKey(
          currentUser.id,
          currentUser.org_id || "",
          "welcome_dismissed",
        ),
        "true",
      );
    } catch {
      // Ignore
    }
  }, [currentUser.id, currentUser.org_id]);

  const nextStep = useCallback(() => {
    if (currentStepIndex < totalSteps - 1) {
      const nextIdx = currentStepIndex + 1;
      setCurrentStepIndex(nextIdx);
      const nextTarget = steps[nextIdx];
      if (nextTarget && location.pathname !== nextTarget.route) {
        navigate(nextTarget.route);
      }
    } else {
      finishTour();
    }
  }, [
    currentStepIndex,
    totalSteps,
    location.pathname,
    navigate,
    finishTour,
    steps,
  ]);

  const prevStep = useCallback(() => {
    if (currentStepIndex > 0) {
      const prevIdx = currentStepIndex - 1;
      setCurrentStepIndex(prevIdx);
      const prevTarget = steps[prevIdx];
      if (prevTarget && location.pathname !== prevTarget.route) {
        navigate(prevTarget.route);
      }
    }
  }, [currentStepIndex, location.pathname, navigate, steps]);

  const goToStep = useCallback(
    (stepIndex: number) => {
      if (stepIndex >= 0 && stepIndex < totalSteps) {
        setCurrentStepIndex(stepIndex);
        const target = steps[stepIndex];
        if (target && location.pathname !== target.route) {
          navigate(target.route);
        }
      }
    },
    [totalSteps, location.pathname, navigate, steps],
  );

  const restartTour = useCallback(() => {
    startTour(0);
  }, [startTour]);

  const openHelp = useCallback(
    (tab: "screen" | "overview" | "glossary" | "faq" = "screen") => {
      setActiveHelpTab(tab);
      setIsHelpOpen(true);
    },
    [],
  );

  const closeHelp = useCallback(() => setIsHelpOpen(false), []);

  return (
    <TourContext.Provider
      value={{
        isWelcomeOpen,
        openWelcome,
        closeWelcome,
        dismissWelcomeForever,
        isTourActive,
        isTourPreparing,
        currentStepIndex,
        currentStep,
        steps,
        totalSteps,
        startTour,
        nextStep,
        prevStep,
        goToStep,
        skipTour,
        finishTour,
        restartTour,
        isHelpOpen,
        openHelp,
        closeHelp,
        activeHelpTab,
        setActiveHelpTab,
      }}
    >
      {children}
    </TourContext.Provider>
  );
};

export const useTour = (): TourContextType => {
  const context = useContext(TourContext);
  if (!context) {
    throw new Error("useTour must be used within a TourProvider");
  }
  return context;
};
