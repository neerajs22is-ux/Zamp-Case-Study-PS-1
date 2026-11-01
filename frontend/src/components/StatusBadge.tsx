import React from 'react';
import { 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  Clock, 
  PauseCircle, 
  RefreshCw, 
  ShieldAlert,
  HelpCircle
} from 'lucide-react';
import { statusFor, type StatusInput } from '../utils/statusNormalizer';

interface StatusBadgeProps {
  invoice?: StatusInput | null;
  stage?: string | null;
  decision?: string | null;
  workflow_substatus?: string | null;
  decision_reason?: string | null;
  showIcon?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  invoice,
  stage,
  decision,
  workflow_substatus,
  decision_reason,
  showIcon = true,
  size = 'md',
  className = '',
}) => {
  const normalized = statusFor(
    invoice || {
      stage,
      decision,
      workflow_substatus,
      decision_reason,
    }
  );

  const renderIcon = () => {
    const iconSizeClass = size === 'sm' ? 'w-3 h-3' : size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5';
    switch (normalized.iconName) {
      case 'check':
        return <CheckCircle2 className={`${iconSizeClass} shrink-0`} aria-hidden="true" />;
      case 'alert':
        return <AlertTriangle className={`${iconSizeClass} shrink-0`} aria-hidden="true" />;
      case 'x':
        return <XCircle className={`${iconSizeClass} shrink-0`} aria-hidden="true" />;
      case 'pause':
        return <PauseCircle className={`${iconSizeClass} shrink-0`} aria-hidden="true" />;
      case 'refresh':
        return <RefreshCw className={`${iconSizeClass} shrink-0 animate-spin`} aria-hidden="true" />;
      case 'shield':
        return <ShieldAlert className={`${iconSizeClass} shrink-0`} aria-hidden="true" />;
      case 'clock':
        return <Clock className={`${iconSizeClass} shrink-0`} aria-hidden="true" />;
      default:
        return <HelpCircle className={`${iconSizeClass} shrink-0`} aria-hidden="true" />;
    }
  };

  const sizeClasses = {
    sm: 'text-[11px] px-2 py-0.5 gap-1 font-medium',
    md: 'text-xs px-2.5 py-1 gap-1.5 font-medium',
    lg: 'text-sm px-3 py-1.5 gap-2 font-medium',
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border transition-colors ${sizeClasses[size]} ${normalized.badgeClass} ${className}`}
      title={normalized.reason}
      role="status"
    >
      {showIcon && renderIcon()}
      <span className="truncate">{normalized.label}</span>
    </span>
  );
};
