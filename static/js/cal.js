/* Fechas locales en formato AAAA-MM-DD (sin zonas horarias: el menú trabaja con días de calendario). */
export const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const parse = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
export const addDays = (d, n) => { const x = new Date(d.getFullYear(), d.getMonth(), d.getDate() + n); return x; };
export const mondayOf = (d) => addDays(d, -((d.getDay() + 6) % 7));
export const monthStart = (d) => new Date(d.getFullYear(), d.getMonth(), 1);
export const monthEnd = (d) => new Date(d.getFullYear(), d.getMonth() + 1, 0);
export const today = () => iso(new Date());
const f = (o) => new Intl.DateTimeFormat("es", o);
export const fmtLong = (d) => f({ weekday: "long", day: "numeric", month: "long" }).format(d);
export const fmtShort = (d) => f({ day: "numeric", month: "short" }).format(d);
export const fmtWeekday = (d) => f({ weekday: "short" }).format(d).replace(".", "");
export const fmtMonth = (d) => f({ month: "long", year: "numeric" }).format(d);
export const rangeFor = (mode, cursor) => {
  if (mode === "day") return [iso(cursor), iso(cursor)];
  if (mode === "week") { const m = mondayOf(cursor); return [iso(m), iso(addDays(m, 6))]; }
  const first = mondayOf(monthStart(cursor));
  return [iso(first), iso(addDays(first, 41))];   // 6 semanas completas (≤ 62 días)
};
export const step = (mode, cursor, dir) => (mode === "day" ? addDays(cursor, dir) : mode === "week" ? addDays(cursor, 7 * dir) : new Date(cursor.getFullYear(), cursor.getMonth() + dir, 1));
