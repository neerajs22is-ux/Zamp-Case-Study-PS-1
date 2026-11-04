import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

export interface TourStep {
  step: number;
  totalSteps: number;
  route: string;
  targetSelector?: string;
  title: string;
  summary: string;
  details: string;
  badge: string;
  badgeTone?: 'neutral' | 'success' | 'warning' | 'error' | 'info' | 'purple';
  tip?: string;
}

export const TOUR_STEPS: TourStep[] = [
  {
    step: 1,
    totalSteps: 8,
    route: '/today',
    targetSelector: '[data-tour="today-kpi-bar"]',
    title: "Today's AP Operations Pulse",
    summary: 'High-level operational overview of pending invoices and financial exposure.',
    details: 'The Daily Triad organizes your workload into three key metrics: invoices needing immediate attention, verified bills cleared and ready for sign-off, and your touchless automation rate. It also tracks statutory MSME liability so you never miss a mandatory 45-day payment window.',
    badge: 'Operational Pulse',
    badgeTone: 'info',
    tip: 'Click any KPI card to jump directly to the pre-filtered invoice queue.',
  },
  {
    step: 2,
    totalSteps: 8,
    route: '/invoices',
    targetSelector: '[data-tour="inbox-queue-tabs"]',
    title: 'Invoice Inbox & Work Queues',
    summary: 'Pre-filtered operational queues for managing invoice processing.',
    details: 'Invoices are organized into focused queues: Needs Attention (blocked by discrepancies), Ready for Approval (passed 3-way match), Waiting on Evidence (missing PO or GRN), and Approved. You can filter by Indian Fiscal Year (FY) and calendar month, or upload new invoice PDFs using drag-and-drop.',
    badge: 'Work Queues',
    badgeTone: 'purple',
    tip: 'Use the pre-filtered tabs instead of complex manual search queries to find pending work fast.',
  },
  {
    step: 3,
    totalSteps: 8,
    route: '/invoices/inv_d76401c096d0',
    targetSelector: '[data-tour="workspace-split"]',
    title: '50/50 Invoice Review Workspace',
    summary: 'Side-by-side verification comparing original document against extracted records.',
    details: 'The left pane displays the original invoice document with pan, zoom, and cryptographic SHA-256 fingerprint verification. The right pane displays structured vendor information, GSTIN, invoice dates, and the authoritative review verdict.',
    badge: 'Review Workspace',
    badgeTone: 'info',
    tip: 'The compact verdict strip above the line items summarizes the match outcome in 48px without obscuring data.',
  },
  {
    step: 4,
    totalSteps: 8,
    route: '/invoices/inv_d76401c096d0',
    targetSelector: '[data-tour="policy-gates-trigger"]',
    title: '7 Deterministic Policy Gates',
    summary: 'Automated governance checks evaluated against supplier invoice, PO, GRN, and QC.',
    details: 'Checks include Vendor Onboarding, GSTIN Match, Mathematical Summation, Duplicate Detection, 3-Way Match, Price & Quantity Tolerances, and Statutory MSME Due Dates. Each gate clearly shows Passed, Failed, Unavailable, or Not Checked with supporting proof.',
    badge: 'Policy Governance',
    badgeTone: 'success',
    tip: 'Click the "Gates" button in the top toolbar anytime to open the full progressive disclosure policy drawer.',
  },
  {
    step: 5,
    totalSteps: 8,
    route: '/invoices/inv_d76401c096d0',
    targetSelector: '[data-tour="reconciliation-flow"]',
    title: 'Line-by-Line 4-Way Reconciliation',
    summary: 'Direct comparison of Invoice items against PO, Goods Receipt (GRN), and Quality Check (QC).',
    details: 'Every billed item is matched against physical receipt and purchase orders. A strict 0.00% quantity shortage tolerance is enforced, while unit prices allow up to ±1.50% variance for statutory fuel or commodity adjustments. Operators can correct OCR misreads with mandatory audit reasons.',
    badge: '4-Way Match',
    badgeTone: 'info',
    tip: 'Discrepancies automatically display recommended debit notes or supplier correction actions.',
  },
  {
    step: 6,
    totalSteps: 8,
    route: '/exceptions',
    targetSelector: '[data-tour="exceptions-table"]',
    title: 'Exception Triage & Resolution',
    summary: 'Prioritized queue for invoices blocked by quantity shortages or rate variances.',
    details: 'When an invoice fails automated checks, it enters the Exceptions Triage queue. Invoices are prioritized by discrepancy severity and statutory MSME deadlines. AP Leads can assign discrepancies to specific buyers or AP specialists for investigation.',
    badge: 'Exception Triage',
    badgeTone: 'warning',
    tip: 'Statutory MSME invoices highlight days remaining to prevent compound interest non-compliance penalties.',
  },
  {
    step: 7,
    totalSteps: 8,
    route: '/approvals',
    targetSelector: '[data-tour="approvals-table"]',
    title: 'High-Value Dual Governance (≥ ₹5,00,000)',
    summary: 'Statutory two-person authorization workflow enforcing separation of duties.',
    details: 'Invoices exceeding ₹5,00,000 require two independent sign-offs: Step 1 (Primary AP Specialist review) and Step 2 (Financial Controller authorization). Anti-self-approval is strictly enforced. Internal AP approval records sign-off; bank disbursements are handled downstream by treasury.',
    badge: 'Dual Control',
    badgeTone: 'purple',
    tip: 'AP approval confirms invoice validity; it does NOT directly trigger bank disbursements.',
  },
  {
    step: 8,
    totalSteps: 8,
    route: '/audit',
    targetSelector: '[data-tour="audit-table"]',
    title: 'Immutable Cryptographic Audit Trail',
    summary: 'Permanent append-only ledger tracking every action, correction, and state change.',
    details: 'Every automated verification, line item correction, review approval, and user authorization is permanently recorded with timestamps, actor IDs, roles, and correlation hashes. Invoices can be audited anytime, and compliance teams can export complete CSV reports with one click.',
    badge: 'Audit & Provenance',
    badgeTone: 'success',
    tip: 'Click "Details" on any audit row to inspect the cryptographic correlation ID and state transition diff.',
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
  currentStepIndex: number;
  currentStep: TourStep;
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
  openHelp: (tab?: 'screen' | 'overview' | 'glossary' | 'faq') => void;
  closeHelp: () => void;
  activeHelpTab: 'screen' | 'overview' | 'glossary' | 'faq';
  setActiveHelpTab: (tab: 'screen' | 'overview' | 'glossary' | 'faq') => void;
}

const TourContext = createContext<TourContextType | undefined>(undefined);

export const TourProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();

  // Welcome modal state
  const [isWelcomeOpen, setIsWelcomeOpen] = useState<boolean>(false);

  // Tour state
  const [isTourActive, setIsTourActive] = useState<boolean>(false);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);

  // Help drawer state
  const [isHelpOpen, setIsHelpOpen] = useState<boolean>(false);
  const [activeHelpTab, setActiveHelpTab] = useState<'screen' | 'overview' | 'glossary' | 'faq'>('screen');

  // Check initial visit on mount
  useEffect(() => {
    try {
      const welcomeDismissed = localStorage.getItem('ap_onboarding_welcome_dismissed');
      const tourCompleted = localStorage.getItem('ap_onboarding_tour_completed');
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
  }, []);

  const openWelcome = useCallback(() => setIsWelcomeOpen(true), []);
  const closeWelcome = useCallback(() => setIsWelcomeOpen(false), []);
  const dismissWelcomeForever = useCallback(() => {
    setIsWelcomeOpen(false);
    try {
      localStorage.setItem('ap_onboarding_welcome_dismissed', 'true');
    } catch {
      // Ignore
    }
  }, []);

  const currentStep = TOUR_STEPS[currentStepIndex] || TOUR_STEPS[0];
  const totalSteps = TOUR_STEPS.length;

  const startTour = useCallback((fromStep: number = 0) => {
    setIsWelcomeOpen(false);
    setIsHelpOpen(false);
    setCurrentStepIndex(fromStep);
    setIsTourActive(true);
    
    // Navigate to step route if needed
    const target = TOUR_STEPS[fromStep];
    if (target && location.pathname !== target.route) {
      navigate(target.route);
    }
  }, [location.pathname, navigate]);

  const finishTour = useCallback(() => {
    setIsTourActive(false);
    try {
      localStorage.setItem('ap_onboarding_tour_completed', 'true');
      localStorage.setItem('ap_onboarding_welcome_dismissed', 'true');
    } catch {
      // Ignore
    }
  }, []);

  const skipTour = useCallback(() => {
    setIsTourActive(false);
    try {
      localStorage.setItem('ap_onboarding_tour_completed', 'true');
      localStorage.setItem('ap_onboarding_welcome_dismissed', 'true');
    } catch {
      // Ignore
    }
  }, []);

  const nextStep = useCallback(() => {
    if (currentStepIndex < totalSteps - 1) {
      const nextIdx = currentStepIndex + 1;
      setCurrentStepIndex(nextIdx);
      const nextTarget = TOUR_STEPS[nextIdx];
      if (nextTarget && location.pathname !== nextTarget.route) {
        navigate(nextTarget.route);
      }
    } else {
      finishTour();
    }
  }, [currentStepIndex, totalSteps, location.pathname, navigate, finishTour]);

  const prevStep = useCallback(() => {
    if (currentStepIndex > 0) {
      const prevIdx = currentStepIndex - 1;
      setCurrentStepIndex(prevIdx);
      const prevTarget = TOUR_STEPS[prevIdx];
      if (prevTarget && location.pathname !== prevTarget.route) {
        navigate(prevTarget.route);
      }
    }
  }, [currentStepIndex, location.pathname, navigate]);

  const goToStep = useCallback((stepIndex: number) => {
    if (stepIndex >= 0 && stepIndex < totalSteps) {
      setCurrentStepIndex(stepIndex);
      const target = TOUR_STEPS[stepIndex];
      if (target && location.pathname !== target.route) {
        navigate(target.route);
      }
    }
  }, [totalSteps, location.pathname, navigate]);

  const restartTour = useCallback(() => {
    startTour(0);
  }, [startTour]);

  const openHelp = useCallback((tab: 'screen' | 'overview' | 'glossary' | 'faq' = 'screen') => {
    setActiveHelpTab(tab);
    setIsHelpOpen(true);
  }, []);

  const closeHelp = useCallback(() => setIsHelpOpen(false), []);

  return (
    <TourContext.Provider
      value={{
        isWelcomeOpen,
        openWelcome,
        closeWelcome,
        dismissWelcomeForever,
        isTourActive,
        currentStepIndex,
        currentStep,
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
    throw new Error('useTour must be used within a TourProvider');
  }
  return context;
};
