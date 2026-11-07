import { useDialogFocus } from "../hooks/useDialogFocus";
import { ScreenPath } from "../components/ScreenPath";
import "./ManagementPages.css";
import React, { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
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
  ArrowRight,
  ShieldCheck,
  Info,
} from "lucide-react";
import { api } from "../api/client";
import { ErrorState, LoadingState } from "../components/ui";
import type { SourceRecordsData } from "../types";
import { formatCurrency } from "../utils/currency";

type ActiveTab = "vendors" | "pos" | "grns" | "qc";

export const SourceRecordsPage: React.FC = () => {
  const [data, setData] = useState<SourceRecordsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>("vendors");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPo, setSelectedPo] = useState<any | null>(null);

  const poDialogRef = useDialogFocus(Boolean(selectedPo), () =>
    setSelectedPo(null),
  );

  const loadRecords = async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const res = await api.getSourceRecords();
      setData(res);
    } catch (err: any) {
      console.error("Failed to load source records:", err);
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRecords();
  }, []);

  const formatINR = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    }).format(val);
  };

  const filteredVendors = useMemo(() => {
    if (!data?.vendors) return [];
    if (!searchQuery.trim()) return data.vendors;
    const q = searchQuery.toLowerCase();
    return data.vendors.filter(
      (v) =>
        v.legal_name.toLowerCase().includes(q) ||
        v.vendor_code.toLowerCase().includes(q) ||
        (v.pan && v.pan.toLowerCase().includes(q)),
    );
  }, [data?.vendors, searchQuery]);

  const filteredPOs = useMemo(() => {
    if (!data?.purchase_orders) return [];
    if (!searchQuery.trim()) return data.purchase_orders;
    const q = searchQuery.toLowerCase();
    return data.purchase_orders.filter(
      (po) =>
        po.po_number.toLowerCase().includes(q) ||
        po.vendor_code.toLowerCase().includes(q) ||
        (po.status && po.status.toLowerCase().includes(q)),
    );
  }, [data?.purchase_orders, searchQuery]);

  const filteredGRNs = useMemo(() => {
    if (!data?.goods_receipts) return [];
    if (!searchQuery.trim()) return data.goods_receipts;
    const q = searchQuery.toLowerCase();
    return data.goods_receipts.filter(
      (grn) =>
        grn.grn_number.toLowerCase().includes(q) ||
        grn.po_number.toLowerCase().includes(q),
    );
  }, [data?.goods_receipts, searchQuery]);

  const filteredQC = useMemo(() => {
    if (!data?.quality_records) return [];
    if (!searchQuery.trim()) return data.quality_records;
    const q = searchQuery.toLowerCase();
    return data.quality_records.filter(
      (qc) =>
        qc.qc_certificate_number.toLowerCase().includes(q) ||
        qc.grn_number.toLowerCase().includes(q),
    );
  }, [data?.quality_records, searchQuery]);

  // Executive Metrics Calculations
  const totalPoAuthorized = useMemo(() => {
    if (!data?.purchase_orders) return 0;
    return data.purchase_orders.reduce(
      (sum, po) => sum + (po.currency === "INR" ? (po.total_authorized || 0) : 0),
      0,
    );
  }, [data?.purchase_orders]);

  const totalPoRemaining = useMemo(() => {
    if (!data?.purchase_orders) return 0;
    return data.purchase_orders.reduce(
      (sum, po) => sum + (po.currency === "INR" ? (po.remaining_balance || 0) : 0),
      0,
    );
  }, [data?.purchase_orders]);

  const msmeCount = useMemo(() => {
    if (!data?.vendors) return 0;
    return data.vendors.filter((v) => v.msme_registered).length;
  }, [data?.vendors]);

  const linkedGrnsForSelectedPo = useMemo(() => {
    if (!selectedPo || !data?.goods_receipts) return [];
    return data.goods_receipts.filter(
      (g) => g.po_number === selectedPo.po_number,
    );
  }, [selectedPo, data?.goods_receipts]);

  const totalRecordsCount =
    (data?.vendors?.length || 0) +
    (data?.purchase_orders?.length || 0) +
    (data?.goods_receipts?.length || 0) +
    (data?.quality_records?.length || 0);

  if (!data) {
    return (
      <div
        data-tour="reference-records"
        className="management-page space-y-5 max-w-6xl mx-auto"
      >
        <h1 className="text-xl font-bold text-slate-900 dark:text-white">
          Procurement records
        </h1>
        {loading ? (
          <LoadingState label="Loading procurement records..." />
        ) : loadError ? (
          <ErrorState
            title="Could not load procurement records"
            message="The records could not be retrieved. Try again."
            onRetry={loadRecords}
          />
        ) : null}
      </div>
    );
  }

  return (
    <div className="management-page space-y-5 max-w-6xl mx-auto">
      {/* Header */}
      <div
        data-tour="reference-records"
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800"
      >
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
              <Database className="w-5 h-5" />
            </span>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Procurement records
            </h1>
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${
                data?.is_live_sync
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40"
                  : "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-400 dark:border-sky-800/40"
              }`}
            >
              Source: {data?.origin_system || "Unavailable"}
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Review the supplier, purchase order, receipt and inspection records
            used for matching. Records are read-only here.
          </p>
        </div>

        <button
          onClick={loadRecords}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-2xs disabled:opacity-50"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`}
          />
          Refresh records
        </button>
      </div>

      <ScreenPath
        title="The evidence used for matching"
        links={[{ to: "/invoices", label: "Find an invoice" }]}
      >
        Purchase orders record what was agreed. Goods receipts record what
        arrived. Inspection records describe acceptance. Compare these saved
        records with an invoice; changes are made in the source system.
      </ScreenPath>

      {loadError && (
        <ErrorState
          title="Could not refresh procurement records"
          message="Previously loaded records are shown and may be out of date."
          onRetry={loadRecords}
        />
      )}

      {/* Procurement Portfolio Metric Strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Supplier records</span>
            <Building2 className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-slate-900 dark:text-white font-mono tabular-nums">
            {data?.vendors?.length || 0}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {msmeCount} MSME Registered
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Purchase order records</span>
            <FileCheck2 className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-emerald-600 dark:text-emerald-400 font-mono tabular-nums">
            {data?.purchase_orders?.length || 0}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            Status shown on each order
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Total PO Authorized</span>
            <ShieldCheck className="w-4 h-4 text-sky-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-slate-900 dark:text-white font-mono tabular-nums">
            {formatINR(totalPoAuthorized)}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            INR orders only; foreign or unknown currencies excluded
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Remaining PO Balance</span>
            <Layers className="w-4 h-4 text-amber-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-indigo-600 dark:text-indigo-400 font-mono tabular-nums">
            {formatINR(totalPoRemaining)}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            INR orders only; foreign or unknown currencies excluded
          </div>
        </div>
      </div>

      {/* Provenance Disclosure Banner */}
      {data && (
        <div className="bg-sky-50/70 dark:bg-sky-950/20 border border-sky-200/80 dark:border-sky-900/40 rounded-xl p-3 text-xs flex items-start gap-2.5 shadow-2xs">
          <Info className="w-4 h-4 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5" />
          <div className="text-slate-700 dark:text-slate-300 space-y-0.5 leading-relaxed">
            <span className="font-semibold text-slate-900 dark:text-slate-100">
              Source and provenance:
            </span>{" "}
            {data.origin_system || "Unavailable"} ·{" "}
            {data.provenance || "Provenance unavailable"}. Records are read-only
            here. A snapshot is a saved copy and may not include later changes.
          </div>
        </div>
      )}

      {/* Tabs and Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Navigation Tabs */}
        <div className="flex items-center gap-1 p-1 bg-slate-100 dark:bg-slate-800/60 rounded-xl border border-slate-200/70 dark:border-slate-700/50 text-xs overflow-x-auto whitespace-nowrap max-w-full">
          <button
            aria-pressed={activeTab === "vendors"}
            onClick={() => setActiveTab("vendors")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === "vendors"
                ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs border border-slate-200/60 dark:border-slate-700"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
            }`}
          >
            <Building2 className="w-3.5 h-3.5 text-indigo-500" />
            <span>Vendors</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-200/80 dark:bg-slate-800 font-mono">
              {data?.vendors?.length || 0}
            </span>
          </button>

          <button
            aria-pressed={activeTab === "pos"}
            onClick={() => setActiveTab("pos")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === "pos"
                ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs border border-slate-200/60 dark:border-slate-700"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
            }`}
          >
            <FileCheck2 className="w-3.5 h-3.5 text-emerald-500" />
            <span>Purchase Orders</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-200/80 dark:bg-slate-800 font-mono">
              {data?.purchase_orders?.length || 0}
            </span>
          </button>

          <button
            aria-pressed={activeTab === "grns"}
            onClick={() => setActiveTab("grns")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === "grns"
                ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs border border-slate-200/60 dark:border-slate-700"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
            }`}
          >
            <PackageCheck className="w-3.5 h-3.5 text-sky-500" />
            <span>Goods Receipts</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-200/80 dark:bg-slate-800 font-mono">
              {data?.goods_receipts?.length || 0}
            </span>
          </button>

          <button
            aria-pressed={activeTab === "qc"}
            onClick={() => setActiveTab("qc")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === "qc"
                ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs border border-slate-200/60 dark:border-slate-700"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
            }`}
          >
            <BadgeCheck className="w-3.5 h-3.5 text-amber-500" />
            <span>Quality Inspection</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-200/80 dark:bg-slate-800 font-mono">
              {data?.quality_records?.length || 0}
            </span>
          </button>
        </div>

        {/* Live Filter Input */}
        <div className="relative w-full sm:w-64">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            aria-label="Search the selected reference records"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={`Search ${{ vendors: "suppliers", pos: "purchase orders", grns: "goods receipts", qc: "inspections" }[activeTab]}…`}
            className="w-full pl-8 pr-7 py-1.5 text-xs rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 shadow-2xs transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xs overflow-hidden">
        {totalRecordsCount === 0 && !loading ? (
          <div className="py-16 text-center text-xs space-y-3 px-4">
            <Layers className="w-10 h-10 text-slate-300 dark:text-slate-600 mx-auto" />
            <div className="font-semibold text-slate-700 dark:text-slate-300 text-sm">
              No ERP reference data loaded
            </div>
            <p className="text-slate-500 dark:text-slate-400 max-w-md mx-auto leading-relaxed">
              No procurement snapshots have been synchronized into this tenant
              workspace. ERP synchronization requires connector credentials.
            </p>
            <div className="pt-2">
              <Link
                to="/settings/connections"
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 text-white font-semibold hover:bg-indigo-500 transition-colors shadow-2xs"
              >
                <span>Check Integration Status</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        ) : (
          <div>
            {/* Tab 1: Vendors */}
            {activeTab === "vendors" && (
              <div className="overflow-x-auto">
                {filteredVendors.length === 0 ? (
                  <div className="py-12 text-center text-xs text-slate-500 dark:text-slate-400">
                    No vendor records match &quot;{searchQuery}&quot;.
                  </div>
                ) : (
                  <table className="w-full text-left text-xs min-w-[680px]">
                    <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold uppercase tracking-wider sticky top-0 backdrop-blur-xs">
                      <tr>
                        <th className="py-2.5 px-4">Vendor Code</th>
                        <th className="py-2.5 px-4">Legal Entity Name</th>
                        <th className="py-2.5 px-4">PAN Number</th>
                        <th className="py-2.5 px-4">MSME Registration</th>
                        <th className="py-2.5 px-4 text-right">
                          Bank Verification
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                      {filteredVendors.map((v) => (
                        <tr
                          key={v.id}
                          className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors"
                        >
                          <td className="py-3 px-4 font-mono font-bold text-indigo-600 dark:text-indigo-400">
                            {v.vendor_code}
                          </td>
                          <td className="py-3 px-4 font-medium text-slate-900 dark:text-white">
                            {v.legal_name}
                          </td>
                          <td className="py-3 px-4 font-mono text-slate-600 dark:text-slate-300">
                            {v.pan || "—"}
                          </td>
                          <td className="py-3 px-4">
                            {v.msme_registered ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40 font-mono">
                                MSME: {v.msme_category || "REGISTERED"}
                              </span>
                            ) : (
                              <span className="text-slate-400 dark:text-slate-500 text-[11px]">
                                Non-MSME
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right">
                            {v.bank_verified ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-sky-50 text-sky-700 border border-sky-200 dark:bg-sky-950/40 dark:text-sky-400 dark:border-sky-800/40">
                                <ShieldCheck className="w-3 h-3" />
                                Verified
                              </span>
                            ) : (
                              <span className="text-slate-400 text-[11px]">
                                Unverified
                              </span>
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
            {activeTab === "pos" && (
              <div className="overflow-x-auto">
                {filteredPOs.length === 0 ? (
                  <div className="py-12 text-center text-xs text-slate-500 dark:text-slate-400">
                    No purchase orders match &quot;{searchQuery}&quot;.
                  </div>
                ) : (
                  <table className="w-full text-left text-xs min-w-[720px]">
                    <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold uppercase tracking-wider sticky top-0 backdrop-blur-xs">
                      <tr>
                        <th className="py-2.5 px-4">PO Number</th>
                        <th className="py-2.5 px-4">Vendor Code</th>
                        <th className="py-2.5 px-4 text-right">
                          Total Authorized
                        </th>
                        <th className="py-2.5 px-4 text-right">
                          Remaining Balance
                        </th>
                        <th className="py-2.5 px-4">Status</th>
                        <th className="py-2.5 px-4 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                      {filteredPOs.map((po) => (
                        <tr
                          key={po.id}
                          onClick={() => setSelectedPo(po)}
                          className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors cursor-pointer group"
                        >
                          <td className="py-3 px-4 font-mono font-bold text-slate-900 dark:text-white">
                            {po.po_number}
                          </td>
                          <td className="py-3 px-4 font-mono text-slate-600 dark:text-slate-300">
                            {po.vendor_code}
                          </td>
                          <td className="py-3 px-4 text-right font-medium text-slate-900 dark:text-white tabular-nums font-mono">
                            {formatCurrency(po.total_authorized, po.currency)}
                          </td>
                          <td className="py-3 px-4 text-right font-bold text-indigo-600 dark:text-indigo-400 tabular-nums font-mono">
                            {formatCurrency(po.remaining_balance, po.currency)}
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border font-mono ${po.status === "APPROVED" ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40" : "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700"}`}
                            >
                              {po.status || "Unavailable"}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right">
                            <span className="text-xs text-indigo-600 dark:text-indigo-400 font-semibold group-hover:underline inline-flex items-center gap-1">
                              View details <ArrowRight className="w-3 h-3" />
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
            {activeTab === "grns" && (
              <div className="overflow-x-auto">
                {filteredGRNs.length === 0 ? (
                  <div className="py-16 text-center text-xs space-y-2 px-4">
                    <PackageCheck className="w-8 h-8 text-slate-400 dark:text-slate-500 mx-auto" />
                    <div className="font-semibold text-slate-700 dark:text-slate-300">
                      No standalone Goods Receipt Note (GRN) records in current
                      snapshot
                    </div>
                    <p className="text-slate-500 max-w-md mx-auto leading-relaxed text-[11px]">
                      In this evaluation workspace, goods receipt data is
                      ingested alongside purchase order line items and verified
                      during Gate #3 (GRN Receipt Confirmed) matching.
                    </p>
                  </div>
                ) : (
                  <table className="w-full text-left text-xs min-w-[640px]">
                    <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold uppercase tracking-wider">
                      <tr>
                        <th className="py-2.5 px-4">GRN Number</th>
                        <th className="py-2.5 px-4">Purchase Order</th>
                        <th className="py-2.5 px-4">Received Date</th>
                        <th className="py-2.5 px-4 text-right">
                          Retrieved Snapshot
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                      {filteredGRNs.map((grn) => (
                        <tr
                          key={grn.id}
                          className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors"
                        >
                          <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                            {grn.grn_number}
                          </td>
                          <td className="py-3 px-4 text-slate-600 dark:text-slate-300">
                            {grn.po_number}
                          </td>
                          <td className="py-3 px-4 text-slate-700 dark:text-slate-300 font-sans">
                            {grn.received_date
                              ? new Date(grn.received_date).toLocaleDateString(
                                  "en-IN",
                                )
                              : "—"}
                          </td>
                          <td className="py-3 px-4 text-right text-slate-400 text-[11px]">
                            {grn.retrieved_at
                              ? new Date(grn.retrieved_at).toLocaleString(
                                  "en-IN",
                                  {
                                    hour: "2-digit",
                                    minute: "2-digit",
                                    day: "numeric",
                                    month: "short",
                                  },
                                )
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {/* Tab 4: Quality Records */}
            {activeTab === "qc" && (
              <div className="overflow-x-auto">
                {filteredQC.length === 0 ? (
                  <div className="py-16 text-center text-xs space-y-2 px-4">
                    <BadgeCheck className="w-8 h-8 text-slate-400 dark:text-slate-500 mx-auto" />
                    <div className="font-semibold text-slate-700 dark:text-slate-300">
                      No standalone Quality Inspection (QC) certificates in
                      current snapshot
                    </div>
                    <p className="text-slate-500 max-w-md mx-auto leading-relaxed text-[11px]">
                      QC certificates are verified during Gate #4 (Quality
                      Inspection Inspection) matching when inbound material
                      requires mandatory metallurgical or dimensional testing.
                    </p>
                  </div>
                ) : (
                  <table className="w-full text-left text-xs min-w-[640px]">
                    <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold uppercase tracking-wider">
                      <tr>
                        <th className="py-2.5 px-4">QC Certificate Number</th>
                        <th className="py-2.5 px-4">GRN Reference</th>
                        <th className="py-2.5 px-4">Inspection Status</th>
                        <th className="py-2.5 px-4 text-right">
                          Retrieved Snapshot
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                      {filteredQC.map((qc) => (
                        <tr
                          key={qc.id}
                          className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors"
                        >
                          <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                            {qc.qc_certificate_number}
                          </td>
                          <td className="py-3 px-4 text-slate-600 dark:text-slate-300">
                            {qc.grn_number}
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border ${
                                ["ACCEPTED", "PASS", "PASSED"].includes(
                                  qc.overall_status,
                                )
                                  ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40"
                                  : ["REJECTED", "FAIL", "FAILED"].includes(
                                        qc.overall_status,
                                      )
                                    ? "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800/40"
                                    : "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700"
                              }`}
                            >
                              {qc.overall_status || "Unavailable"}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right text-slate-400 text-[11px]">
                            {qc.retrieved_at
                              ? new Date(qc.retrieved_at).toLocaleString(
                                  "en-IN",
                                  {
                                    hour: "2-digit",
                                    minute: "2-digit",
                                    day: "numeric",
                                    month: "short",
                                  },
                                )
                              : "—"}
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
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-xs flex justify-end animate-in fade-in duration-150">
          <div
            ref={poDialogRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label="Purchase order details"
            className="product-dialog w-full max-w-lg bg-white dark:bg-slate-900 h-full shadow-2xl border-l border-slate-200 dark:border-slate-800 flex flex-col"
          >
            <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileCheck2 className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                <h2 className="text-sm font-bold text-slate-900 dark:text-white font-mono">
                  Purchase Order: {selectedPo.po_number}
                </h2>
              </div>
              <button
                onClick={() => setSelectedPo(null)}
                className="p-2 min-w-[40px] min-h-[40px] flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                aria-label="Close purchase order details"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 overflow-y-auto flex-1 space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-xl border border-slate-100 dark:border-slate-800/60">
                  <span className="text-slate-400 text-[11px] block">
                    Vendor Code
                  </span>
                  <span className="font-mono font-bold text-slate-900 dark:text-white text-sm">
                    {selectedPo.vendor_code}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-xl border border-slate-100 dark:border-slate-800/60">
                  <span className="text-slate-400 text-[11px] block">
                    PO Status
                  </span>
                  <span
                    className={`font-mono font-bold text-sm ${selectedPo.status === "APPROVED" ? "text-emerald-700 dark:text-emerald-400" : "text-slate-700 dark:text-slate-300"}`}
                  >
                    {selectedPo.status || "Unavailable"}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-xl border border-slate-100 dark:border-slate-800/60">
                  <span className="text-slate-400 text-[11px] block">
                    Total Authorized
                  </span>
                  <span className="font-mono font-bold text-slate-900 dark:text-white text-sm tabular-nums">
                    {formatCurrency(selectedPo.total_authorized, selectedPo.currency)}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-xl border border-slate-100 dark:border-slate-800/60">
                  <span className="text-slate-400 text-[11px] block">
                    Remaining Balance
                  </span>
                  <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400 text-sm tabular-nums">
                    {formatCurrency(selectedPo.remaining_balance, selectedPo.currency)}
                  </span>
                </div>
              </div>

              {/* Progress Bar of consumption */}
              <div className="p-3.5 bg-slate-50 dark:bg-slate-950/60 rounded-xl border border-slate-100 dark:border-slate-800/60 space-y-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-slate-500 font-medium">
                    Authorization Utilization
                  </span>
                  <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                    {selectedPo.total_authorized > 0
                      ? (
                          ((selectedPo.total_authorized -
                            selectedPo.remaining_balance) /
                            selectedPo.total_authorized) *
                          100
                        ).toFixed(1) + "%"
                      : "0.0%"}
                  </span>
                </div>
                <div className="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                  <div
                    className="h-full bg-indigo-600 rounded-full transition-all"
                    style={{
                      width: `${Math.min(
                        100,
                        Math.max(
                          0,
                          selectedPo.total_authorized > 0
                            ? ((selectedPo.total_authorized -
                                selectedPo.remaining_balance) /
                                selectedPo.total_authorized) *
                                100
                            : 0,
                        ),
                      )}%`,
                    }}
                  />
                </div>
              </div>

              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2.5">
                  Linked Goods Receipts ({linkedGrnsForSelectedPo.length})
                </h3>
                {linkedGrnsForSelectedPo.length === 0 ? (
                  <p className="text-slate-400 italic">
                    No GRN records linked to this purchase order in current
                    snapshot.
                  </p>
                ) : (
                  <div className="divide-y divide-slate-100 dark:divide-slate-800 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
                    {linkedGrnsForSelectedPo.map((grn) => (
                      <div
                        key={grn.id}
                        className="p-3 flex items-center justify-between font-mono bg-slate-50/50 dark:bg-slate-950/30"
                      >
                        <div>
                          <div className="font-bold text-slate-800 dark:text-slate-200">
                            {grn.grn_number}
                          </div>
                          <div className="text-[10px] text-slate-400 font-sans">
                            Recv:{" "}
                            {grn.received_date
                              ? new Date(grn.received_date).toLocaleDateString(
                                  "en-IN",
                                )
                              : "—"}
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

              <div className="p-3 bg-slate-50 dark:bg-slate-950/40 rounded-xl border border-slate-100 dark:border-slate-800/60 text-[11px] text-slate-500 space-y-1">
                <div className="flex items-center gap-1.5 font-medium text-slate-700 dark:text-slate-300">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                  Anti-Tamper Invariant
                </div>
                <p className="leading-relaxed">
                  These are read-only reference snapshots. Make changes in the
                  source system and refresh available records here. A snapshot
                  may not include later source changes.
                </p>
              </div>
            </div>

            <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/50 flex justify-end">
              <button
                onClick={() => setSelectedPo(null)}
                className="px-4 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors shadow-2xs"
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
