/**
 * limitUtilisation.js
 * Shared utility for limit utilisation calculation and colour coding.
 * Used by MetricsRow and RollRiskTab.
 *
 * Formula: IM / (LIMIT + VIX margin)
 */

export const LIMIT = 20_000_000;

/**
 * Compute utilisation ratio.
 * @param {number|null} margin  - Current initial margin
 * @param {number}      vix     - VIX margin (0 if unavailable)
 * @returns {number|null}
 */
export function calcUtilisation(margin, vix = 0) {
  if (margin == null) return null;
  return margin / (LIMIT + vix);
}

/**
 * Return a colour string based on utilisation ratio.
 * ≥ 90% → red, ≥ 75% → orange, otherwise default text colour.
 * @param {number|null} ratio
 * @returns {string}
 */
export function utilisationColour(ratio) {
  if (ratio == null)  return "text.primary";
  if (ratio >= 0.9)   return "#ef4444";
  if (ratio >= 0.75)  return "#f97316";
  return "text.primary";
}
