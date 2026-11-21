export function num(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function percent(value, digits = 0) {
  if (value === null || value === undefined) return "-";
  const sign = value > 0 ? "+" : "";
  return sign + Number(value).toFixed(digits) + "%";
}

export function dateTime(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function minutesText(value) {
  if (value === null || value === undefined) return "-";
  if (value < 1) return "<1 min";
  return Math.round(value) + " min";
}

export const LEANING = {
  higher_than_usual: { label: "Higher than your usual", tone: "amber" },
  lower_than_usual: { label: "Lower than your usual", tone: "cyan" },
  unclear: { label: "Unclear", tone: "slate" },
};

export const CONFIDENCE = {
  very_low: "Very low (model not validated for this target)",
  low: "Low (score close to the decision boundary)",
  moderate: "Moderate",
  moderate_high: "Moderate-high",
};
