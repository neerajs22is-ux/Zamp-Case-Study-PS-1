/**
 * Central Policy & Configuration Constants (Phase 1 Truth Pass).
 *
 * Authoritative fallback values matching backend runtime configuration:
 * - backend/core/config.py: DUAL_APPROVAL_THRESHOLD_INR = 500000.00
 * - backend/core/config.py: RATE_TOLERANCE_PERCENT = 1.50
 * - backend/core/config.py: ROUNDING_TOLERANCE_INR = 20.00
 */

export interface SystemPolicy {
  dual_approval_threshold_inr: number;
  rate_tolerance_percent: number;
  rounding_tolerance_inr: number;
}

export const DEFAULT_POLICY: SystemPolicy = {
  dual_approval_threshold_inr: 500000.0,
  rate_tolerance_percent: 1.50,
  rounding_tolerance_inr: 20.0,
};
