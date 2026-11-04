import React from 'react';

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'error' | 'info' | 'purple';
export type BadgeSize = 'sm' | 'md' | 'lg';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  size?: BadgeSize;
  dot?: boolean;
  icon?: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  tone = 'neutral',
  size = 'md',
  dot = false,
  icon,
  className = '',
  ...props
}) => {
  const toneStyles: Record<BadgeTone, { badge: string; dot: string }> = {
    neutral: {
      badge:
        'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800/80 dark:text-slate-300 dark:border-slate-700',
      dot: 'bg-slate-400 dark:bg-slate-500',
    },
    success: {
      badge:
        'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/60',
      dot: 'bg-emerald-500',
    },
    warning: {
      badge:
        'bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/60',
      dot: 'bg-amber-500',
    },
    error: {
      badge:
        'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/60',
      dot: 'bg-rose-500',
    },
    info: {
      badge:
        'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300 dark:border-sky-800/60',
      dot: 'bg-sky-500',
    },
    purple: {
      badge:
        'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800/60',
      dot: 'bg-purple-500',
    },
  };

  const sizeStyles: Record<BadgeSize, string> = {
    sm: 'text-[11px] px-2 py-0.5 gap-1 font-medium',
    md: 'text-xs px-2.5 py-0.5 gap-1.5 font-medium',
    lg: 'text-sm px-3 py-1 gap-2 font-medium',
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border transition-colors select-none ${toneStyles[tone].badge} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {dot && (
        <span
          className={`w-1.5 h-1.5 rounded-full shrink-0 ${toneStyles[tone].dot}`}
          aria-hidden="true"
        />
      )}
      {icon && <span className="shrink-0">{icon}</span>}
      <span className="truncate">{children}</span>
    </span>
  );
};
