import React, { useEffect, useState } from 'react';
import { 
  Database, 
  RefreshCw, 
  Building2, 
  FileCheck2, 
  PackageCheck, 
  BadgeCheck,
  ShieldAlert
} from 'lucide-react';
import { api } from '../api/client';
import type { SourceRecordsData } from '../types';

export const SourceRecordsPage: React.FC = () => {
  const [data, setData] = useState<SourceRecordsData | null>(null);
  const [loading, setLoading] = useState(true);

  const loadRecords = async () => {
    setLoading(true);
    try {
      const res = await api.getSourceRecords();
      setData(res);
    } catch (err: any) {
      console.error(err);
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <Database className="w-5 h-5 text-indigo-400" />
            Authoritative ERP Source Records (Read-Only)
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Synchronized snapshot from SAP S/4HANA (Vendors, Purchase Orders, Goods Receipts, QC).
          </p>
        </div>
        <button
          onClick={loadRecords}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-900 border border-slate-800 text-xs text-slate-300 hover:bg-slate-800 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Snapshots
        </button>
      </div>

      {/* Read-Only Invariant Callout */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-3 text-xs flex items-start gap-2.5">
        <ShieldAlert className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
        <div className="text-slate-300 space-y-0.5">
          <span className="font-semibold text-slate-200">Read-Only Isolation Boundary:</span> Phase 1 ERP connectivity is strictly read-only. No local editing is permitted on procurement records, preventing fictitious master data mutations.
        </div>
      </div>

      {/* Grid of ERP Snapshots */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Vendors Snapshot */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
            <h2 className="text-xs font-semibold text-slate-200 uppercase flex items-center gap-2">
              <Building2 className="w-4 h-4 text-indigo-400" />
              Verified Vendors ({data?.vendors.length || 0})
            </h2>
            <span className="text-[11px] font-mono text-slate-500">SAP Master</span>
          </div>

          {(!data?.vendors || data.vendors.length === 0) ? (
            <div className="text-slate-500 text-center py-8 text-xs">
              Zero vendor records. SAP vendor master sync required.
            </div>
          ) : (
            <div className="divide-y divide-slate-800/60 text-xs">
              {data.vendors.map((v) => (
                <div key={v.id} className="py-2.5 flex items-center justify-between">
                  <div>
                    <div className="font-medium text-slate-200">{v.legal_name}</div>
                    <div className="text-[10px] text-slate-500 font-mono">Code: {v.vendor_code} | PAN: {v.pan || '—'}</div>
                  </div>
                  <div className="text-right">
                    {v.msme_registered ? (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        MSME {v.msme_category || 'REGISTERED'}
                      </span>
                    ) : (
                      <span className="text-[10px] font-mono text-slate-500">NON-MSME</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Purchase Orders Snapshot */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
            <h2 className="text-xs font-semibold text-slate-200 uppercase flex items-center gap-2">
              <FileCheck2 className="w-4 h-4 text-indigo-400" />
              Purchase Orders ({data?.purchase_orders.length || 0})
            </h2>
            <span className="text-[11px] font-mono text-slate-500">SAP PO Ledger</span>
          </div>

          {(!data?.purchase_orders || data.purchase_orders.length === 0) ? (
            <div className="text-slate-500 text-center py-8 text-xs">
              Zero purchase orders. SAP PO sync required.
            </div>
          ) : (
            <div className="divide-y divide-slate-800/60 text-xs font-mono">
              {data.purchase_orders.map((po) => (
                <div key={po.id} className="py-2.5 flex items-center justify-between">
                  <div>
                    <div className="text-slate-200 font-bold">{po.po_number}</div>
                    <div className="text-[10px] text-slate-500 font-sans">Vendor: {po.vendor_code}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-slate-100 tabular-nums">{formatINR(po.remaining_balance)} rem</div>
                    <div className="text-[10px] text-slate-500">of {formatINR(po.total_authorized)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Goods Receipts (GRN) Snapshot */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
            <h2 className="text-xs font-semibold text-slate-200 uppercase flex items-center gap-2">
              <PackageCheck className="w-4 h-4 text-indigo-400" />
              Goods Receipts Note ({data?.goods_receipts.length || 0})
            </h2>
            <span className="text-[11px] font-mono text-slate-500">SAP GRN Ledger</span>
          </div>

          {(!data?.goods_receipts || data.goods_receipts.length === 0) ? (
            <div className="text-slate-500 text-center py-8 text-xs">
              Zero GRN records. SAP goods receipt sync required.
            </div>
          ) : (
            <div className="divide-y divide-slate-800/60 text-xs font-mono">
              {data.goods_receipts.map((grn) => (
                <div key={grn.id} className="py-2.5 flex items-center justify-between">
                  <div>
                    <div className="text-slate-200 font-bold">{grn.grn_number}</div>
                    <div className="text-[10px] text-slate-500">PO: {grn.po_number}</div>
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Recv: {grn.received_date.substring(0, 10)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Quality Records Snapshot */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
            <h2 className="text-xs font-semibold text-slate-200 uppercase flex items-center gap-2">
              <BadgeCheck className="w-4 h-4 text-indigo-400" />
              Quality Inspection Records ({data?.quality_records.length || 0})
            </h2>
            <span className="text-[11px] font-mono text-slate-500">SAP QM</span>
          </div>

          {(!data?.quality_records || data.quality_records.length === 0) ? (
            <div className="text-slate-500 text-center py-8 text-xs">
              Zero quality control records. SAP QM sync required.
            </div>
          ) : (
            <div className="divide-y divide-slate-800/60 text-xs font-mono">
              {data.quality_records.map((qc) => (
                <div key={qc.id} className="py-2.5 flex items-center justify-between">
                  <div>
                    <div className="text-slate-200 font-bold">{qc.qc_certificate_number}</div>
                    <div className="text-[10px] text-slate-500">GRN: {qc.grn_number}</div>
                  </div>
                  <div>
                    <span className={`text-[10px] px-2 py-0.5 rounded ${
                      qc.overall_status === 'PASSED' 
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                        : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                    }`}>
                      {qc.overall_status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
