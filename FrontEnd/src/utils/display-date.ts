export const LOGIC_YEAR = 2026;
export const DISPLAY_YEAR = 2026;

export function displayYear(year: number): number {
  return year === LOGIC_YEAR ? DISPLAY_YEAR : year;
}

export function shiftDateForDisplay(dateStr: string): string {
  if (!dateStr) return '';
  return dateStr.replace(/\b2026\b/g, String(DISPLAY_YEAR));
}

export function shiftDateToLogic(dateStr: string): string {
  if (!dateStr) return '';
  return dateStr.replace(/\b2026\b/g, String(LOGIC_YEAR));
}

export function formatDateForDisplay(dStr: string): string {
  if (!dStr) return '';
  if (dStr.includes('T')) {
    return shiftDateForDisplay(dStr.split('T')[0]);
  }
  try {
    const parts = dStr.split(' ');
    const dateParts = parts[0].split('/');
    if (dateParts.length === 3) {
      const day = dateParts[0].padStart(2, '0');
      const month = dateParts[1].padStart(2, '0');
      const year = dateParts[2];
      return shiftDateForDisplay(`${year}-${month}-${day}`);
    }
  } catch {}
  return shiftDateForDisplay(dStr);
}

export function formatDateFromDateForDisplay(d: Date): string {
  const y = d.getFullYear();
  const m = (d.getMonth() + 1).toString().padStart(2, '0');
  const day = d.getDate().toString().padStart(2, '0');
  return shiftDateForDisplay(`${y}-${m}-${day}`);
}
