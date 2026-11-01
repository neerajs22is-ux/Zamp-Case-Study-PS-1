export type UserRole = 
  | 'AP_ASSOCIATE'
  | 'AP_LEAD'
  | 'CONTROLLER'
  | 'CATEGORY_MANAGER'
  | 'AUDITOR'
  | 'SYSTEM_ADMIN';

export interface AuthenticatedUser {
  id: string;
  email: string;
  name: string;
  role?: UserRole | null;
  org_id?: string | null;
  org_name?: string | null;
  is_provisioned: boolean;
  status: 'ACTIVE' | 'UNPROVISIONED';
  available_orgs?: { id: string; name: string }[];
  legal_entity_ids?: string[];
}

export interface UserInvitation {
  invitation_id: string;
  org_id: string;
  email: string;
  role: UserRole;
  expires_at: string;
  invitation_token: string;
}

export interface AccessRequest {
  id: string;
  org_id: string;
  user_id?: string;
  email?: string;
  full_name?: string;
  requested_role: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  review_reason?: string | null;
  created_at: string;
  reviewed_at?: string | null;
}

export interface SubsystemHealth {
  status: 'CONNECTED' | 'NOT_CONFIGURED' | 'DEGRADED' | 'BLOCKED' | 'ERROR';
  message: string;
  readiness: boolean;
  [key: string]: any;
}

export interface HealthResponse {
  app_name: string;
  app_env: string;
  overall_status: 'READY' | 'SETUP_REQUIRED' | 'BLOCKED';
  timestamp: string;
  subsystems: {
    database: SubsystemHealth;
    object_storage: SubsystemHealth;
    identity_provider: SubsystemHealth;
    gmail_ingestion: SubsystemHealth;
    sap_erp: SubsystemHealth;
  };
}

export interface DashboardMetrics {
  status: 'active' | 'unavailable';
  reason?: string;
  timestamp: string;
  timezone: string;
  summary?: {
    total_invoices: number;
    open_exceptions: number;
    blocked_value_inr: number;
    msme_exposure_count: number;
    touchless_rate_pct: number | null;
    active_ingestion_jobs: number;
  };
  stages?: Record<string, number>;
  decisions?: Record<string, number>;
  metric_definitions?: Record<string, string>;
}

export interface InvoiceItem {
  id: string;
  invoice_number: string | null;
  vendor_name: string;
  vendor_gstin: string | null;
  po_reference: string | null;
  total_amount: number | null;
  currency: string;
  stage: string;
  decision: string;
  decision_reason: string | null;
  msme_statutory_deadline: string | null;
  msme_deadline_status: string | null;
  created_at: string;
  updated_at: string;
}

export interface InboxResponse {
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: InvoiceItem[];
  message?: string;
}

export interface ExceptionItem {
  exception_id: string;
  invoice_id: string;
  invoice_number: string | null;
  vendor_name: string | null;
  blocking_gate_number: number;
  blocking_gate_name: string;
  exposure_amount_inr: number;
  msme_statutory_deadline: string | null;
  assigned_user_id: string | null;
  created_at: string;
}

export interface ExceptionsResponse {
  total_count: number;
  items: ExceptionItem[];
  message?: string;
}

export interface SourceRecordsData {
  origin_system: string;
  is_live_sync?: boolean;
  provenance?: string;
  vendors: Array<{
    id: string;
    vendor_code: string;
    legal_name: string;
    pan: string | null;
    msme_registered: boolean;
    msme_category: string | null;
    bank_verified: boolean;
  }>;
  purchase_orders: Array<{
    id: string;
    po_number: string;
    vendor_code: string;
    total_authorized: number;
    remaining_balance: number;
    currency: string;
    status: string;
    retrieved_at: string;
  }>;
  goods_receipts: Array<{
    id: string;
    grn_number: string;
    po_number: string;
    received_date: string;
    retrieved_at: string;
  }>;
  quality_records: Array<{
    id: string;
    qc_certificate_number: string;
    grn_number: string;
    overall_status: string;
    retrieved_at: string;
  }>;
  message?: string;
}

export interface AuditEventItem {
  id: string;
  invoice_id: string | null;
  actor_id: string;
  actor_role: string;
  action: string;
  reason: string | null;
  correlation_id: string | null;
  before_state: any;
  after_state: any;
  source_reference: string | null;
  timestamp: string;
}

export interface AuditResponse {
  total_count: number;
  items: AuditEventItem[];
  message?: string;
}

export interface DocumentMetadata {
  id: string;
  org_id: string;
  invoice_id?: string | null;
  filename: string;
  mime_type: string;
  file_size_bytes: number;
  sha256_hash: string;
  storage_provider: string;
  storage_key: string;
  is_original: boolean;
  is_deleted: boolean;
  deleted_at?: string | null;
  uploaded_at: string;
}

export type UploadLifecycleStatus = 
  | 'Idle'
  | 'Uploading'
  | 'Validating'
  | 'Processing'
  | 'Ready'
  | 'Failed'
  | 'Duplicate detected'
  | 'Access denied';

