import React from 'react';

export const Table = React.forwardRef<
  HTMLTableElement,
  React.TableHTMLAttributes<HTMLTableElement>
>(({ className = '', ...props }, ref) => (
  <div className="w-full overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs">
    <table
      ref={ref}
      className={`w-full caption-bottom text-xs text-left ${className}`}
      {...props}
    />
  </div>
));
Table.displayName = 'Table';

export const TableHeader = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className = '', ...props }, ref) => (
  <thead
    ref={ref}
    className={`bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 ${className}`}
    {...props}
  />
));
TableHeader.displayName = 'TableHeader';

export const TableBody = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className = '', ...props }, ref) => (
  <tbody
    ref={ref}
    className={`divide-y divide-slate-100 dark:divide-slate-850 text-slate-700 dark:text-slate-300 ${className}`}
    {...props}
  />
));
TableBody.displayName = 'TableBody';

export const TableRow = React.forwardRef<
  HTMLTableRowElement,
  React.HTMLAttributes<HTMLTableRowElement> & { isInteractive?: boolean }
>(({ className = '', isInteractive = true, ...props }, ref) => (
  <tr
    ref={ref}
    className={`transition-colors ${
      isInteractive
        ? 'hover:bg-slate-50/80 dark:hover:bg-slate-800/40 cursor-pointer'
        : ''
    } ${className}`}
    {...props}
  />
));
TableRow.displayName = 'TableRow';

export const TableHead = React.forwardRef<
  HTMLTableCellElement,
  React.ThHTMLAttributes<HTMLTableCellElement>
>(({ className = '', ...props }, ref) => (
  <th
    ref={ref}
    className={`px-3.5 py-3 align-middle font-semibold select-none ${className}`}
    {...props}
  />
));
TableHead.displayName = 'TableHead';

export const TableCell = React.forwardRef<
  HTMLTableCellElement,
  React.TdHTMLAttributes<HTMLTableCellElement>
>(({ className = '', ...props }, ref) => (
  <td
    ref={ref}
    className={`px-3.5 py-3 align-middle leading-normal ${className}`}
    {...props}
  />
));
TableCell.displayName = 'TableCell';
