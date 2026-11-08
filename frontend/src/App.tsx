import React, { useEffect, useState, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { TourProvider } from './context/TourContext';
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
import { api, clearSession, setSession, getAuthToken } from './api/client';
import { oauthCallbackParams, supabaseLogout } from './utils/oauth';
import type { AuthenticatedUser, HealthResponse } from './types';
import { ErrorBoundary } from './components/ErrorBoundary';

// Route Wrapper for Invoice Detail with URL parameter binding
const InvoiceDetailWrapper: React.FC<{ user: AuthenticatedUser | null }> = ({ user }) => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  if (!id) {
    return <Navigate to="/invoices" replace />;
  }

  return (
    <ErrorBoundary fallbackTitle="Invoice Detail Unavailable" onReset={() => navigate('/invoices')}>
      <InvoiceDetailPage
        key={id}
        invoiceId={id}
        onBack={() => navigate('/invoices')}
        currentUser={user}
      />
    </ErrorBoundary>
  );
};

// Route Wrapper for Legacy Connections redirect preserving search params
const ConnectionsRedirect: React.FC = () => {
  const [searchParams] = useSearchParams();
  const search = searchParams.toString();
  return <Navigate to={`/settings/connections${search ? `?${search}` : ''}`} replace />;
};

// Route Wrapper for Sandbox Experience redirect
const SandboxRedirect: React.FC = () => {
  useEffect(() => {
    window.location.href = '/sandbox';
  }, []);
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-400">
      <div className="flex items-center space-x-3">
        <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
        <span>Redirecting to AP Command Center Sandbox...</span>
      </div>
    </div>
  );
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
    const { accessToken, refreshToken } = oauthCallbackParams(window.location.search, window.location.hash);
    if (accessToken) {
      setSession(accessToken, refreshToken);
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    }

    // 2. Fetch user profile and health
    fetchUserProfile();
    api.getHealth().then(setHealth).catch(console.error);
  }, [fetchUserProfile]);

  const handleLogout = async () => {
    let logoutError: string | null = null;
    const currentToken = getAuthToken();
    try {
      if (currentToken) {
        const authStatus = await api.getAuthStatus().catch(() => null);
        const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || authStatus?.supabase_url;
        const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || authStatus?.supabase_anon_key;
        if (supabaseUrl && anonKey) {
          await supabaseLogout(supabaseUrl, anonKey, currentToken).catch(() => null);
        }
      }
      await api.logout();
    } catch {
      logoutError = 'Local session cleared, but server-side token revocation failed. The access token may remain valid until expiry.';
    } finally {
      clearSession();
      setUser(null);
      setAuthError(logoutError);
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
      setSession(res.access_token);
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
      <div className={user ? 'min-h-screen bg-slate-50 dark:bg-[#17191c] text-slate-900 dark:text-slate-100 flex flex-col font-sans transition-colors duration-150' : 'auth-page min-h-screen flex flex-col'}>
        <main className={user ? 'flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10' : 'auth-page-main flex-1 w-full px-4 sm:px-6'}>
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
    <TourProvider key={JSON.stringify([user!.id, user!.org_id])} currentUser={user!}>
    <AppShell
      user={user}
      health={health}
      onLogout={handleLogout}
      onSwitchRole={handleDevRoleSwitch}
    >
      <Routes>
        {/* Core Primary Navigation Routes */}
        <Route path="/" element={<Navigate to="/today" replace />} />
        <Route path="/today" element={<DashboardPage onNavigate={(route) => navigate(route === 'inbox' ? '/invoices' : route.startsWith('/') ? route : `/${route}`)} currentUser={user} />} />
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

        {/* Sandbox Demonstration Route */}
        <Route path="/sandbox" element={<SandboxRedirect />} />

        {/* Catch-all fallback */}
        <Route path="*" element={<Navigate to="/today" replace />} />
      </Routes>
    </AppShell>
    </TourProvider>
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
