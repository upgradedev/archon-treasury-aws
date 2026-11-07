export function compactMoney(raw: string | undefined | null): { primary: string; subline: string | null } {
  if (!raw) {
    return { primary: '0.00', subline: null };
  }
  const match = raw.match(/^([A-Z]{3,4}\s+[-0-9.,]+)\s*\(([^)]+)\)$/);
  if (match) {
    return { primary: match[1].trim(), subline: match[2].trim() };
  }
  return { primary: raw, subline: null };
}
