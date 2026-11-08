import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw, ArrowLeft } from "lucide-react";
import { Button, Card } from "./ui";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an unhandled error:", error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 max-w-2xl mx-auto my-8">
          <Card className="border-rose-200 dark:border-rose-900/50 p-6 space-y-4 bg-white dark:bg-slate-900 shadow-md">
            <div className="flex items-center gap-3 text-rose-600 dark:text-rose-400">
              <AlertTriangle className="w-6 h-6 shrink-0" />
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                {this.props.fallbackTitle || "Unable to display this view"}
              </h2>
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              An unexpected error occurred while rendering this invoice or component. The underlying data remains intact.
            </p>
            {this.state.error?.message && (
              <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800 text-xs font-mono text-slate-600 dark:text-slate-300 overflow-x-auto">
                {this.state.error.message}
              </div>
            )}
            <div className="flex items-center gap-3 pt-2">
              <Button
                variant="primary"
                size="sm"
                onClick={this.handleReset}
                leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
              >
                Retry
              </Button>
              {this.props.onReset && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={this.props.onReset}
                  leftIcon={<ArrowLeft className="w-3.5 h-3.5" />}
                >
                  Back to Invoices
                </Button>
              )}
            </div>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}
