import React from 'react';

export interface SectionHeaderProps {
  title: string;
  description?: string;
  count?: number;
  actions?: React.ReactNode;
  className?: string;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  title,
  description,
  count,
  actions,
  className = '',
}) => {
  return (
    <div className={`flex items-center justify-between gap-3 mb-3 ${className}`}>
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            {title}
          </h2>
          {typeof count === 'number' && (
            <span className="px-1.5 py-0.5 rounded-full text-[11px] font-mono font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
              {count}
            </span>
          )}
        </div>
        {description && (
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            {description}
          </p>
        )}
      </div>

      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </div>
  );
};
