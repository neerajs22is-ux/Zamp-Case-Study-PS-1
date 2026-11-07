/** Display an amount only in its recorded currency; no conversion is implied. */
export function formatCurrency(amount?: number | null, currency?: string | null): string {
  if (amount == null) return "—";
  if (!currency) return `${amount} (currency unavailable)`;
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency", currency, maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${amount} ${currency}`;
  }
}
