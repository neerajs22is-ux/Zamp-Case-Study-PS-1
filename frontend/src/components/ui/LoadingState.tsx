import React from 'react';
import { Loader2 } from 'lucide-react';

export interface LoadingStateProps {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  label = 'Loading...',
  size = 'md',
  className = '',
}) => {
  const iconSizes = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  };

  return (
    <div
      className={`flex flex-col items-center justify-center p-8 text-center text-slate-500 dark:text-slate-400 ${className}`}
      role="status"
    >
      <Loader2 className={`${iconSizes[size]} animate-spin text-indigo-600 dark:text-indigo-400 mb-2.5`} />
      <span className="text-xs font-medium">{label}</span>
    </div>
  );
};

export const Skeleton: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div
    className={`animate-pulse rounded bg-slate-200 dark:bg-slate-800 ${className}`}
    aria-hidden="true"
  />
);
