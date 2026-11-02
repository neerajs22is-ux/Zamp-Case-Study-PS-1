import React, { useEffect, useState, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AppShell } from './components/AppShell';
import { AuthScreen } from './components/AuthScreen';
import { DashboardPage } from './pages/DashboardPage';
import { ConnectionsPage } from './pages/ConnectionsPage';
import { InboxPage } from './pages/InboxPage';
import { InvoiceDetailPage } from './pages/InvoiceDetailPage';
import { ApprovalsPage } from './pages/ApprovalsPage';
import { ExceptionsPage } from './pages/ExceptionsPage';
import { SourceRecordsPage } from './pages/SourceRecordsPage';
import { AuditPage } from './pages/AuditPage';
import { AccessManagementPage } from './pages/AccessManagementPage';
import { OnboardingPage } from './pages/OnboardingPage';
import { api, clearAuthToken, setAuthToken, getAuthToken } from './api/client';
import type { AuthenticatedUser, HealthResponse } from './types';

// Route Wrapper for Invoice Detail with URL parameter binding
const InvoiceDetailWrapper: React.FC<{ user: AuthenticatedUser | null }> = ({ user }) => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  if (!id) {
    return <Navigate to="/invoices" replace />;
  }

  return (
    <InvoiceDetailPage
      invoiceId={id}
      onBack={() => navigate('/invoices')}
      currentUser={user}
    />
  );
};

// Route Wrapper for Legacy Connections redirect preserving search params
const ConnectionsRedirect: React.FC = () => {
  const [searchParams] = useSearchParams();
  const search = searchParams.toString();
  return <Navigate to={`/settings/connections${search ? `?${search}` : ''}`} replace />;
};

export const AppContent: React.FC = () => {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [authLoading, setAuthLoading] = useState<boolean>(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const navigate = useNavigate();

  const fetchUserProfile = useCallback(async () => {
    try {
      setAuthLoading(true);
      setAuthError(null);
      const profile = await api.getCurrentUser();
      setUser(profile);
    } catch (err: any) {
      setUser(null);
      if (getAuthToken()) {
        setAuthError(err.message || 'Session verification failed or token expired.');
      }
    } finally {
      setAuthLoading(false);
    }
  }, []);

  useEffect(() => {
    // 1. Check for OAuth callback in URL hash (from Supabase Auth Google sign-in)
    const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const accessToken = hashParams.get('access_token');
    if (accessToken) {
      setAuthToken(accessToken);
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    }

    // 2. Fetch user profile and health
    fetchUserProfile();
    api.getHealth().then(setHealth).catch(console.error);
  }, [fetchUserProfile]);

  const handleLogout = async () => {
    try {
      await api.logout().catch(() => {});
    } finally {
      clearAuthToken();
      setUser(null);
      setAuthError(null);
      navigate('/today');
    }
  };

  const handleDevRoleSwitch = async (role: string) => {
    const roleEmailMap: Record<string, string> = {
      AP_ASSOCIATE: 'sme_associate@company.internal',
      AP_LEAD: 'sme_lead@company.internal',
      CONTROLLER: 'sme_controller@company.internal',
      AUDITOR: 'sme_auditor@company.internal',
      SYSTEM_ADMIN: 'admin@company.internal',
    };
    const email = roleEmailMap[role] || 'sme_lead@company.internal';
    try {
      setAuthLoading(true);
      const res = await api.getDevSession(email, user?.org_id || 'org_sme_eval');
      setAuthToken(res.access_token);
      await fetchUserProfile();
    } catch (err: any) {
      console.error('Role switch failed:', err);
    } finally {
      setAuthLoading(false);
    }
  };

  const isFullyProvisioned = Boolean(user && user.is_provisioned && user.org_id);

  if (!isFullyProvisioned) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-[#090d16] text-slate-900 dark:text-slate-100 flex flex-col font-sans transition-colors duration-150">
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <AuthScreen
            user={user}
            loading={authLoading}
            error={authError}
            onRefreshUser={fetchUserProfile}
            onLogout={handleLogout}
          />
        </main>
      </div>
    );
  }

  return (
    <AppShell
      user={user}
      health={health}
      onLogout={handleLogout}
      onSwitchRole={handleDevRoleSwitch}
    >
      <Routes>
        {/* Core Primary Navigation Routes */}
        <Route path="/" element={<Navigate to="/today" replace />} />
        <Route path="/today" element={<DashboardPage onNavigate={(route) => navigate(route === 'inbox' ? '/invoices' : `/${route}`)} currentUser={user} />} />
        <Route path="/setup" element={<OnboardingPage currentUser={user} />} />
        <Route path="/invoices" element={<InboxPage onSelectInvoice={(id) => navigate(`/invoices/${id}`)} />} />
        <Route path="/invoices/:id" element={<InvoiceDetailWrapper user={user} />} />
        <Route path="/approvals" element={<ApprovalsPage currentUser={user} />} />
        <Route path="/audit" element={<AuditPage currentUser={user} />} />

        {/* Settings Navigation Routes */}
        <Route path="/settings/connections" element={<ConnectionsPage currentUser={user} />} />
        <Route path="/settings/reference-data" element={<SourceRecordsPage />} />
        <Route path="/settings/team" element={<AccessManagementPage currentUser={user!} />} />

        {/* Backward-Compatible Route Redirects */}
        <Route path="/dashboard" element={<Navigate to="/today" replace />} />
        <Route path="/inbox" element={<Navigate to="/invoices" replace />} />
        <Route path="/exceptions" element={<ExceptionsPage onSelectInvoice={(id) => navigate(`/invoices/${id}`)} />} />
        <Route path="/connections" element={<ConnectionsRedirect />} />
        <Route path="/vendors" element={<Navigate to="/settings/reference-data" replace />} />
        <Route path="/source-records" element={<Navigate to="/settings/reference-data" replace />} />
        <Route path="/access-management" element={<Navigate to="/settings/team" replace />} />

        {/* Catch-all fallback */}
        <Route path="*" element={<Navigate to="/today" replace />} />
      </Routes>
    </AppShell>
  );
};

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </ThemeProvider>
  );
};

export default App;
