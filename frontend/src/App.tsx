import React, { useEffect, useState, useCallback } from 'react';
import { Navigation } from './components/Navigation';
import { AuthScreen } from './components/AuthScreen';
import { DashboardPage } from './pages/DashboardPage';
import { ConnectionsPage } from './pages/ConnectionsPage';
import { InboxPage } from './pages/InboxPage';
import { InvoiceDetailPage } from './pages/InvoiceDetailPage';
import { ExceptionsPage } from './pages/ExceptionsPage';
import { SourceRecordsPage } from './pages/SourceRecordsPage';
import { AuditPage } from './pages/AuditPage';
import { AccessManagementPage } from './pages/AccessManagementPage';
import { api, clearAuthToken, setAuthToken, getAuthToken } from './api/client';
import type { AuthenticatedUser, HealthResponse } from './types';

export const App: React.FC = () => {
  const [currentRoute, setCurrentRoute] = useState<string>('dashboard');
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<string | null>(null);
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [authLoading, setAuthLoading] = useState<boolean>(true);
  const [authError, setAuthError] = useState<string | null>(null);

  const fetchUserProfile = useCallback(async () => {
    try {
      setAuthLoading(true);
      setAuthError(null);
      const profile = await api.getCurrentUser();
      setUser(profile);
    } catch (err: any) {
      setUser(null);
      // Only set error message if a token was attempted or it's not a generic unauthenticated state
      if (getAuthToken()) {
        setAuthError(err.message || 'Session verification failed or token expired.');
      }
    } finally {
      setAuthLoading(false);
    }
  }, []);

  useEffect(() => {
    // 1. Check for OAuth callback in URL hash (e.g. #access_token=... from Supabase Auth Google OAuth)
    const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const accessToken = hashParams.get('access_token');
    if (accessToken) {
      setAuthToken(accessToken);
      // Clean up hash fragment without reloading
      window.history.replaceState(null, '', window.location.pathname);
    }

    // 2. Fetch user session and system health
    fetchUserProfile();
    api.getHealth().then(setHealth).catch(console.error);

    // 3. Read window route hash if present
    const cleanHash = window.location.hash.replace('#/', '');
    if (cleanHash.startsWith('invoices/')) {
      const id = cleanHash.replace('invoices/', '');
      setSelectedInvoiceId(id);
      setCurrentRoute('invoice-detail');
    } else if (cleanHash && !cleanHash.startsWith('access_token=')) {
      setCurrentRoute(cleanHash);
    }
  }, [fetchUserProfile]);

  const handleNavigate = (route: string) => {
    setSelectedInvoiceId(null);
    setCurrentRoute(route);
    window.location.hash = `#/${route}`;
  };

  const handleSelectInvoice = (invoiceId: string) => {
    setSelectedInvoiceId(invoiceId);
    setCurrentRoute('invoice-detail');
    window.location.hash = `#/invoices/${invoiceId}`;
  };

  const handleLogout = async () => {
    try {
      await api.logout().catch(() => {});
    } finally {
      clearAuthToken();
      setUser(null);
      setAuthError(null);
      setCurrentRoute('dashboard');
    }
  };

  // If user is unauthenticated or unprovisioned, render AuthScreen
  const isFullyProvisioned = user && user.is_provisioned && user.org_id;

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col font-sans selection:bg-indigo-600 selection:text-white">
      {/* Shell Header & Navigation */}
      <Navigation
        currentRoute={currentRoute}
        onNavigate={handleNavigate}
        user={user}
        health={health}
        onLogout={user ? handleLogout : undefined}
      />

      {/* Main Content Viewport */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {!isFullyProvisioned ? (
          <AuthScreen
            user={user}
            loading={authLoading}
            error={authError}
            onRefreshUser={fetchUserProfile}
            onLogout={handleLogout}
          />
        ) : (
          <>
            {currentRoute === 'dashboard' && <DashboardPage onNavigate={handleNavigate} />}
            {currentRoute === 'connections' && <ConnectionsPage />}
            {currentRoute === 'inbox' && <InboxPage onSelectInvoice={handleSelectInvoice} />}
            {currentRoute === 'invoice-detail' && selectedInvoiceId && (
              <InvoiceDetailPage
                invoiceId={selectedInvoiceId}
                onBack={() => handleNavigate('inbox')}
              />
            )}
            {currentRoute === 'exceptions' && <ExceptionsPage onSelectInvoice={handleSelectInvoice} />}
            {currentRoute === 'source-records' && <SourceRecordsPage />}
            {currentRoute === 'audit' && <AuditPage />}
            {currentRoute === 'access-management' && <AccessManagementPage currentUser={user} />}
          </>
        )}
      </main>

      {/* Footer / Status Ledger */}
      <footer className="border-t border-slate-900 bg-slate-950/60 py-3 text-center text-[11px] text-slate-500 font-mono">
        Autonomous AP Command Center — Binding Production Engineering Specification &copy; 2026. All rights reserved.
      </footer>
    </div>
  );
};

export default App;