import React, { useEffect, useMemo, useState } from 'react';
import { 
  RefreshCw, 
  User, 
  ChevronRight,
  ShieldAlert
} from 'lucide-react';
import { api } from '../api/client';
import { 
  PageHeader, 
  Card, 
  Button, 
  Badge, 
  SearchInput, 
  FilterTabs, 
  Table, 
  TableHeader, 
  TableBody, 
  TableRow, 
  TableHead, 
  TableCell, 
  Modal, 
  LoadingState, 
  EmptyState 
} from '../components/ui';
import type { FilterTabItem } from '../components/ui';
import type { ExceptionItem } from '../types';

interface ExceptionsPageProps {
  onSelectInvoice: (invoiceId: string) => void;
}

interface TeamMember {
  id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
}

type ExceptionTab = 'all' | 'critical' | 'high_exposure' | 'unassigned';

export const ExceptionsPage: React.FC<ExceptionsPageProps> = ({ onSelectInvoice }) => {
  const [items, setItems] = useState<ExceptionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<ExceptionTab>('all');
  
  // Reassign Modal State
  const [reassignModalItem, setReassignModalItem] = useState<ExceptionItem | null>(null);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [selectedOwnerId, setSelectedOwnerId] = useState<string>('');
  const [reassignReason, setReassignReason] = useState<string>('');
  const [reassignLoading, setReassignLoading] = useState<boolean>(false);
  const [reassignSuccessMsg, setReassignSuccessMsg] = useState<string | null>(null);

  const loadExceptions = async () => {
    setLoading(true);
    try {
      const res = await api.getExceptions();
      setItems(res.items || []);
    } catch (err: any) {
      console.error('Failed to load exceptions:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadTeamMembers = async () => {
    try {
      const res = await api.getMembers();
      if (res && res.items) {
        setTeamMembers(res.items.filter((m: any) => m.is_active));
      }
    } catch (err) {
      console.debug('Failed to load team members:', err);
    }
  };

  useEffect(() => {
    loadExceptions();
    loadTeamMembers();
  }, []);

  const formatINR = (val: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(val);
  };

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      // Tab filter
      if (activeTab === 'critical' && item.blocking_gate_number < 4) return false;
      if (activeTab === 'high_exposure' && item.exposure_amount_inr < 500000) return false;
      if (activeTab === 'unassigned' && item.assigned_user_id) return false;

      // Search filter
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase().trim();
      return (
        (item.invoice_number || '').toLowerCase().includes(q) ||
        (item.invoice_id || '').toLowerCase().includes(q) ||
        (item.vendor_name || '').toLowerCase().includes(q) ||
        (item.blocking_gate_name || '').toLowerCase().includes(q) ||
        (item.assigned_user_id || '').toLowerCase().includes(q)
      );
    });
  }, [items, activeTab, searchQuery]);

  const handleOpenReassign = (e: React.MouseEvent, item: ExceptionItem) => {
    e.stopPropagation();
    setReassignModalItem(item);
    setSelectedOwnerId(item.assigned_user_id || '');
    setReassignReason('');
    setReassignSuccessMsg(null);
  };

  const handleConfirmReassign = async () => {
    if (!reassignModalItem || !selectedOwnerId) return;
    setReassignLoading(true);
    try {
      await api.reassignException(
        reassignModalItem.exception_id,
        selectedOwnerId,
        reassignReason || 'Task routed for operational investigation.'
      );
      setReassignSuccessMsg('Exception reassigned successfully.');
      setTimeout(() => {
        setReassignModalItem(null);
        loadExceptions();
      }, 700);
    } catch (err: any) {
      alert(`Reassign failed: ${err.message}`);
    } finally {
      setReassignLoading(false);
    }
  };

  const tabs: FilterTabItem<ExceptionTab>[] = [
    { id: 'all', label: 'All Exceptions', count: items.length },
    { 
      id: 'critical', 
      label: 'Core Discrepancies', 
      count: items.filter((i) => i.blocking_gate_number >= 4).length,
      badgeTone: 'error'
    },
    { 
      id: 'high_exposure', 
      label: 'High Exposure (≥ ₹5L)', 
      count: items.filter((i) => i.exposure_amount_inr >= 500000).length,
      badgeTone: 'warning'
    },
    { 
      id: 'unassigned', 
      label: 'Unassigned', 
      count: items.filter((i) => !i.assigned_user_id).length,
      badgeTone: 'neutral'
    },
  ];

  return (
    <div className="space-y-5">
      {/* 1. Page Header */}
      <PageHeader
        title="Exception Triage Queue"
        description="Invoices with quantity shortages, rate variances, missing receipts, or tax mismatches requiring resolution."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={loadExceptions}
            isLoading={loading}
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>
        }
      />

      {/* 2. Filter Tabs & Search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <FilterTabs
          tabs={tabs}
          activeTab={activeTab}
          onChange={setActiveTab}
        />

        <SearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Search by invoice, vendor, issue..."
          className="w-full sm:w-64"
        />
      </div>

      {/* 3. Exceptions Table */}
      <Card className="overflow-hidden">
        {loading && items.length === 0 ? (
          <LoadingState label="Loading exception queue..." className="py-16" />
        ) : filteredItems.length === 0 ? (
          <EmptyState
            title="No exceptions in this queue"
            description={searchQuery ? `No records matched "${searchQuery}".` : "All received bills have passed policy verification."}
            className="py-12 border-none bg-transparent"
          />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow isInteractive={false}>
                  <TableHead>Invoice & Supplier</TableHead>
                  <TableHead>Blocking Policy Gate</TableHead>
                  <TableHead className="text-right">Exposure Amount</TableHead>
                  <TableHead>Statutory Deadline</TableHead>
                  <TableHead>Assigned Owner</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredItems.map((item) => (
                  <TableRow
                    key={item.exception_id}
                    onClick={() => onSelectInvoice(item.invoice_id)}
                    className="group"
                  >
                    <TableCell>
                      <div className="font-mono font-semibold text-slate-900 dark:text-white">
                        {item.invoice_number || item.invoice_id}
                      </div>
                      <div className="font-semibold text-slate-800 dark:text-slate-200 text-xs">
                        {item.vendor_name || 'Vendor Unregistered'}
                      </div>
                    </TableCell>

                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <Badge tone="error" size="sm">
                          Gate {item.blocking_gate_number}
                        </Badge>
                        <span className="font-medium text-slate-800 dark:text-slate-200 text-xs">
                          {item.blocking_gate_name}
                        </span>
                      </div>
                    </TableCell>

                    <TableCell className="text-right font-mono font-semibold text-slate-900 dark:text-white tabular-nums">
                      {formatINR(item.exposure_amount_inr)}
                    </TableCell>

                    <TableCell>
                      {item.msme_statutory_deadline ? (
                        <div className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 font-mono">
                          <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                          <span>{new Date(item.msme_statutory_deadline).toLocaleDateString()}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400 text-xs">Standard 30 Days</span>
                      )}
                    </TableCell>

                    <TableCell>
                      <button
                        type="button"
                        onClick={(e) => handleOpenReassign(e, item)}
                        className="inline-flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium cursor-pointer"
                        title="Click to reassign owner"
                      >
                        <User className="w-3.5 h-3.5" />
                        <span>{item.assigned_user_id || 'Assign Owner'}</span>
                      </button>
                    </TableCell>

                    <TableCell className="text-right">
                      <Button
                        variant="secondary"
                        size="xs"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectInvoice(item.invoice_id);
                        }}
                        rightIcon={<ChevronRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5" />}
                      >
                        Resolve
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Card>

      {/* Reassign Modal */}
      {reassignModalItem && (
        <Modal
          isOpen={Boolean(reassignModalItem)}
          onClose={() => setReassignModalItem(null)}
          title="Reassign Exception Ownership"
          description={`Route invoice ${reassignModalItem.invoice_number || reassignModalItem.invoice_id} to an AP team member or buyer.`}
          maxWidth="md"
          footer={
            <div className="flex items-center justify-end gap-2.5 w-full">
              <Button variant="secondary" size="sm" onClick={() => setReassignModalItem(null)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleConfirmReassign}
                isLoading={reassignLoading}
                disabled={!selectedOwnerId}
              >
                Confirm Assignment
              </Button>
            </div>
          }
        >
          <div className="space-y-3 text-xs">
            {reassignSuccessMsg && (
              <div className="p-2.5 rounded-lg bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                {reassignSuccessMsg}
              </div>
            )}

            <div>
              <label className="font-semibold text-slate-800 dark:text-slate-200 block mb-1">
                Select Team Member
              </label>
              <select
                value={selectedOwnerId}
                onChange={(e) => setSelectedOwnerId(e.target.value)}
                className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
              >
                <option value="">-- Choose assignee --</option>
                {teamMembers.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.full_name} ({m.email}) — {m.role}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="font-semibold text-slate-800 dark:text-slate-200 block mb-1">
                Assignment Note
              </label>
              <textarea
                rows={2}
                value={reassignReason}
                onChange={(e) => setReassignReason(e.target.value)}
                placeholder="Reason for routing this discrepancy..."
                className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
              />
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
