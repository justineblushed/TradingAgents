const currencyFormatter = new Intl.NumberFormat("en-CA", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatCurrency(value: number): string {
  return `$${currencyFormatter.format(value)}`;
}

export function formatSignedCurrency(value: number): string {
  return value < 0 ? `-$${currencyFormatter.format(-value)}` : formatCurrency(value);
}
