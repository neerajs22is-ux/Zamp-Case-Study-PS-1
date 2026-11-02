import React, { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { 
  Database, 
  RefreshCw, 
  Building2, 
  FileCheck2, 
  PackageCheck, 
  BadgeCheck,
  Search,
  X,
  Layers,
  ArrowRight
} from 'lucide-react';
import { api } from '../api/client';
import type { SourceRecordsData } from '../types';

type ActiveTab = 'vendors' | 'pos' | 'grns' | 'qc';

export const SourceRecordsPage: React.FC = () => {
  const [data, setData] = useState<SourceRecordsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<ActiveTab>('vendors');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPo, setSelectedPo] = useState<any | null>(null);

  const loadRecords = async () => {
    setLoading(true);
    try {
      const res = await api.getSourceRecords();
      setData(res);
    } catch (err: any) {
      console.error('Failed to load source records:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRecords();
  }, []);

  const formatINR = (val: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(val);
  };

  const filteredVendors = useMemo(() => {
    if (!data?.vendors) return [];
    if (!searchQuery.trim()) return data.vendors;
    const q = searchQuery.toLowerCase();
    return data.vendors.filter(v => 
      v.legal_name.toLowerCase().includes(q) ||
      v.vendor_code.toLowerCase().includes(q) ||
      (v.pan && v.pan.toLowerCase().includes(q))
    );
  }, [data?.vendors, searchQuery]);

  const filteredPOs = useMemo(() => {
    if (!data?.purchase_orders) return [];
    if (!searchQuery.trim()) return data.purchase_orders;
    const q = searchQuery.toLowerCase();
    return data.purchase_orders.filter(po => 
      po.po_number.toLowerCase().includes(q) ||
      po.vendor_code.toLowerCase().includes(q)
    );
  }, [data?.purchase_orders, searchQuery]);

  const filteredGRNs = useMemo(() => {
    if (!data?.goods_receipts) return [];
    if (!searchQuery.trim()) return data.goods_receipts;
    const q = searchQuery.toLowerCase();
    return data.goods_receipts.filter(grn => 
      grn.grn_number.toLowerCase().includes(q) ||
      grn.po_number.toLowerCase().includes(q)
    );
  }, [data?.goods_receipts, searchQuery]);

  const filteredQC = useMemo(() => {
    if (!data?.quality_records) return [];
    if (!searchQuery.trim()) return data.quality_records;
    const q = searchQuery.toLowerCase();
    return data.quality_records.filter(qc => 
      qc.qc_certificate_number.toLowerCase().includes(q) ||
      qc.grn_number.toLowerCase().includes(q)
    );
  }, [data?.quality_records, searchQuery]);

  const linkedGrnsForSelectedPo = useMemo(() => {
    if (!selectedPo || !data?.goods_receipts) return [];
    return data.goods_receipts.filter(g => g.po_number === selectedPo.po_number);
  }, [selectedPo, data?.goods_receipts]);

  const totalRecordsCount = (data?.vendors?.length || 0) + 
    (data?.purchase_orders?.length || 0) + 
    (data?.goods_receipts?.length || 0) + 
    (data?.quality_records?.length || 0);

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
              <Database className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
              Authoritative Reference Data
            </h1>
            <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${
              data?.is_live_sync 
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40'
                : 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/40'
            }`}>
              Source: {data?.origin_system || 'Evaluation Dataset'}
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Authoritative master data and procurement snapshots used by the 7-gate validation engine. Local edits are disabled to prevent phantom master data mutations.
          </p>
        </div>

        <button
          onClick={loadRecords}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800/80 transition-colors shadow-sm disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Snapshots
        </button>
      </div>

      {/* Provenance Disclosure Banner */}
      {!data?.is_live_sync && (
        <div className="bg-amber-50/70 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/30 rounded-xl p-3 text-xs flex items-start gap-2.5 shadow-2xs">
          <Layers className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="text-amber-900 dark:text-amber-300">
            <span className="font-semibold">Evaluation Provenance Notice:</span> Live SAP S/4HANA OData synchronization is not provisioned in this environment. Procurement master records are populated from evaluation corpus fixtures (<code className="font-mono">fictional_supplier_master.csv</code>, <code className="font-mono">purchase_orders.csv</code>).
          </div>
        </div>
      )}

      {/* Tabs and Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Navigation Tabs */}
        <div className="flex items-center gap-1 p-1 bg-slate-100 dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800/80 text-xs overflow-x-auto whitespace-nowrap max-w-full">
          <button
            onClick={() => setActiveTab('vendors')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium transition-colors ${
              activeTab === 'vendors'
                ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            <Building2 className="w-3.5 h-3.5 text-indigo-500" />
            <span>Vendors</span>
            <span className="text-[11px] px-1.5 py-0.2 rounded-full bg-slate-200 dark:bg-slate-700 font-mono">
              {data?.vendors?.length || 0}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('pos')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium transition-colors ${
              activeTab === 'pos'
                ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            <FileCheck2 className="w-3.5 h-3.5 text-indigo-500" />
            <span>Purchase Orders</span>
            <span className="text-[11px] px-1.5 py-0.2 rounded-full bg-slate-200 dark:bg-slate-700 font-mono">
              {data?.purchase_orders?.length || 0}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('grns')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium transition-colors ${
              activeTab === 'grns'
                ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            <PackageCheck className="w-3.5 h-3.5 text-indigo-500" />
            <span>Goods Receipts</span>
            <span className="text-[11px] px-1.5 py-0.2 rounded-full bg-slate-200 dark:bg-slate-700 font-mono">
              {data?.goods_receipts?.length || 0}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('qc')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium transition-colors ${
              activeTab === 'qc'
                ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            <BadgeCheck className="w-3.5 h-3.5 text-indigo-500" />
            <span>Quality Inspection</span>
            <span className="text-[11px] px-1.5 py-0.2 rounded-full bg-slate-200 dark:bg-slate-700 font-mono">
              {data?.quality_records?.length || 0}
            </span>
          </button>
        </div>

        {/* Live Filter Input */}
        <div className="relative w-full sm:w-64">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={`Filter ${activeTab}...`}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs text-slate-800 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 shadow-sm"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm overflow-hidden">
        {totalRecordsCount === 0 && !loading ? (
          <div className="py-16 text-center text-xs space-y-3 px-4">
            <Layers className="w-10 h-10 text-slate-300 dark:text-slate-600 mx-auto" />
            <div className="font-semibold text-slate-700 dark:text-slate-300 text-sm">
              No ERP reference data loaded
            </div>
            <p className="text-slate-500 dark:text-slate-400 max-w-md mx-auto leading-relaxed">
              No procurement snapshots have been synchronized into this tenant workspace. ERP synchronization requires connector credentials.
            </p>
            <div className="pt-2">
              <Link
                to="/settings/connections"
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-500 transition-colors shadow-sm"
              >
                <span>Check Integration Status</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        ) : (
          <div>
            {/* Tab 1: Vendors */}
            {activeTab === 'vendors' && (
              <div className="overflow-x-auto">
                {filteredVendors.length === 0 ? (
                  <div className="py-12 text-center text-xs text-slate-500 dark:text-slate-400">
                    No vendor records match &quot;{searchQuery}&quot;.
                  </div>
                ) : (
                  <table className="w-full text-left text-xs min-w-[660px]">
                    <thead className="bg-slate-50 dark:bg-slate-950/60 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px]">
                      <tr>
                        <th className="py-2.5 px-4 font-medium">Vendor Code</th>
                        <th className="py-2.5 px-4 font-medium">Legal Entity Name</th>
                        <th className="py-2.5 px-4 font-medium">PAN</th>
                        <th className="py-2.5 px-4 font-medium">MSME Registration</th>
                        <th className="py-2.5 px-4 font-medium text-right">Bank Verification</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                      {filteredVendors.map((v) => (
                        <tr key={v.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors">
                          <td className="py-3 px-4 font-mono font-semibold text-indigo-600 dark:text-indigo-400">
                            {v.vendor_code}
                          </td>
                          <td className="py-3 px-4 font-medium text-slate-900 dark:text-white">
                            {v.legal_name}
                          </td>
                          <td className="py-3 px-4 font-mono text-slate-600 dark:text-slate-300">
                            {v.pan || '—'}
                          </td>
                          <td className="py-3 px-4">
                            {v.msme_registered ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40 font-mono">
                                MSME: {v.msme_category || 'REGISTERED'}
                              </span>
                            ) : (
                              <span className="text-slate-400 dark:text-slate-500 text-[11px]">Non-MSME</span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right">
                            {v.bank_verified ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-sky-50 text-sky-700 border border-sky-200 dark:bg-sky-950/40 dark:text-sky-400 dark:border-sky-800/40">
                                Verified
                              </span>
                            ) : (
                              <span className="text-slate-400 text-[11px]">Unverified</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {/* Tab 2: Purchase Orders */}
            {activeTab === 'pos' && (
              <div className="overflow-x-auto">
                {filteredPOs.length === 0 ? (
                  <div className="py-12 text-center text-xs text-slate-500 dark:text-slate-400">
                    No purchase orders match &quot;{searchQuery}&quot;.
                  </div>
                ) : (
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 dark:bg-slate-950/60 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px]">
                      <tr>
                        <th className="py-2.5 px-4 font-medium">PO Number</th>
                        <th className="py-2.5 px-4 font-medium">Vendor</th>
                        <th className="py-2.5 px-4 font-medium text-right">Total Authorized</th>
                        <th className="py-2.5 px-4 font-medium text-right">Remaining Balance</th>
                        <th className="py-2.5 px-4 font-medium">Status</th>
                        <th className="py-2.5 px-4 font-medium text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                      {filteredPOs.map((po) => (
                        <tr 
                          key={po.id} 
                          onClick={() => setSelectedPo(po)}
                          className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors cursor-pointer"
                        >
                          <td className="py-3 px-4 font-mono font-bold text-slate-900 dark:text-white">
                            {po.po_number}
                          </td>
                          <td className="py-3 px-4 font-mono text-slate-600 dark:text-slate-300">
                            {po.vendor_code}
                          </td>
                          <td className="py-3 px-4 text-right font-medium text-slate-900 dark:text-white tabular-nums">
                            {formatINR(po.total_authorized)}
                          </td>
                          <td className="py-3 px-4 text-right font-medium text-slate-700 dark:text-slate-300 tabular-nums">
                            {formatINR(po.remaining_balance)}
                          </td>
                          <td className="py-3 px-4">
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700 font-mono">
                              {po.status || 'RELEASED'}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right">
                            <span className="text-xs text-indigo-600 dark:text-indigo-400 font-medium hover:underline inline-flex items-center gap-1">
                              View details
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {/* Tab 3: Goods Receipts */}
            {activeTab === 'grns' && (
              <div className="overflow-x-auto">
                {filteredGRNs.length === 0 ? (
                  <div className="py-12 text-center text-xs text-slate-500 dark:text-slate-400">
                    No goods receipts match &quot;{searchQuery}&quot;.
                  </div>
                ) : (
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 dark:bg-slate-950/60 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px]">
                      <tr>
                        <th className="py-2.5 px-4 font-medium">GRN Number</th>
                        <th className="py-2.5 px-4 font-medium">Purchase Order</th>
                        <th className="py-2.5 px-4 font-medium">Received Date</th>
                        <th className="py-2.5 px-4 font-medium text-right">Retrieved Snapshot</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                      {filteredGRNs.map((grn) => (
                        <tr key={grn.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors">
                          <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                            {grn.grn_number}
                          </td>
                          <td className="py-3 px-4 text-slate-600 dark:text-slate-300">
                            {grn.po_number}
                          </td>
                          <td className="py-3 px-4 text-slate-700 dark:text-slate-300 font-sans">
                            {grn.received_date ? new Date(grn.received_date).toLocaleDateString('en-IN') : '—'}
                          </td>
                          <td className="py-3 px-4 text-right text-slate-400 text-[11px]">
                            {grn.retrieved_at ? new Date(grn.retrieved_at).toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' }) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {/* Tab 4: Quality Records */}
            {activeTab === 'qc' && (
              <div className="overflow-x-auto">
                {filteredQC.length === 0 ? (
                  <div className="py-12 text-center text-xs text-slate-500 dark:text-slate-400">
                    No quality inspection records match &quot;{searchQuery}&quot;.
                  </div>
                ) : (
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 dark:bg-slate-950/60 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px]">
                      <tr>
                        <th className="py-2.5 px-4 font-medium">QC Certificate Number</th>
                        <th className="py-2.5 px-4 font-medium">GRN Reference</th>
                        <th className="py-2.5 px-4 font-medium">Inspection Status</th>
                        <th className="py-2.5 px-4 font-medium text-right">Retrieved Snapshot</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                      {filteredQC.map((qc) => (
                        <tr key={qc.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors">
                          <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                            {qc.qc_certificate_number}
                          </td>
                          <td className="py-3 px-4 text-slate-600 dark:text-slate-300">
                            {qc.grn_number}
                          </td>
                          <td className="py-3 px-4">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border ${
                              qc.overall_status === 'PASSED'
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40'
                                : 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800/40'
                            }`}>
                              {qc.overall_status}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right text-slate-400 text-[11px]">
                            {qc.retrieved_at ? new Date(qc.retrieved_at).toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' }) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* PO Detail Slide-Over Drawer */}
      {selectedPo && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-sm flex justify-end">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 h-full shadow-2xl border-l border-slate-200 dark:border-slate-800 flex flex-col">
            <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileCheck2 className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                  Purchase Order: {selectedPo.po_number}
                </h2>
              </div>
              <button
                onClick={() => setSelectedPo(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 overflow-y-auto flex-1 space-y-5 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-lg border border-slate-100 dark:border-slate-800/60">
                  <span className="text-slate-400 text-[11px] block">Vendor Code</span>
                  <span className="font-mono font-bold text-slate-900 dark:text-white text-sm">{selectedPo.vendor_code}</span>
                </div>
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-lg border border-slate-100 dark:border-slate-800/60">
                  <span className="text-slate-400 text-[11px] block">PO Status</span>
                  <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400 text-sm">{selectedPo.status || 'RELEASED'}</span>
                </div>
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-lg border border-slate-100 dark:border-slate-800/60">
                  <span className="text-slate-400 text-[11px] block">Total Authorized</span>
                  <span className="font-mono font-bold text-slate-900 dark:text-white text-sm tabular-nums">{formatINR(selectedPo.total_authorized)}</span>
                </div>
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-lg border border-slate-100 dark:border-slate-800/60">
                  <span className="text-slate-400 text-[11px] block">Remaining Balance</span>
                  <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400 text-sm tabular-nums">{formatINR(selectedPo.remaining_balance)}</span>
                </div>
              </div>

              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2.5">
                  Linked Goods Receipts ({linkedGrnsForSelectedPo.length})
                </h3>
                {linkedGrnsForSelectedPo.length === 0 ? (
                  <p className="text-slate-400 italic">No GRN records linked to this purchase order.</p>
                ) : (
                  <div className="divide-y divide-slate-100 dark:divide-slate-800 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden">
                    {linkedGrnsForSelectedPo.map((grn) => (
                      <div key={grn.id} className="p-3 flex items-center justify-between font-mono bg-slate-50/50 dark:bg-slate-950/30">
                        <div>
                          <div className="font-bold text-slate-800 dark:text-slate-200">{grn.grn_number}</div>
                          <div className="text-[10px] text-slate-400 font-sans">
                            Recv: {grn.received_date ? new Date(grn.received_date).toLocaleDateString('en-IN') : '—'}
                          </div>
                        </div>
                        <span className="text-[10px] text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-800/40">
                          MATCH ELIGIBLE
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="p-3 bg-slate-50 dark:bg-slate-950/40 rounded-lg border border-slate-100 dark:border-slate-800/60 text-[11px] text-slate-500">
                <span>Retrieved from {data?.is_live_sync ? 'SAP S/4HANA snapshot' : 'procurement reference snapshot'} at </span>
                <span className="font-mono text-slate-700 dark:text-slate-300">
                  {selectedPo.retrieved_at ? new Date(selectedPo.retrieved_at).toLocaleString('en-IN') : 'Synchronized cache'}
                </span>
              </div>
            </div>

            <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/50 flex justify-end">
              <button
                onClick={() => setSelectedPo(null)}
                className="px-4 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-750 transition-colors shadow-sm"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
