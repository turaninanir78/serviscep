export function todayDateString(): string {
  return dateToString(new Date());
}

export function dateToString(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

// Yerlesik bir takvim/date-picker widget'i yerine (native modul + Expo Go
// uyumluluk riski), yeniden planlama icin basit, platformdan bagimsiz bir
// "sonraki N gun" secici kullaniliyor - bir randevuyu yakin bir gune tasima
// akisi icin yeterli ve hem native hem web'de ayni sekilde calisiyor.
export function nextNDates(n: number): string[] {
  const dates: string[] = [];
  const today = new Date();
  for (let i = 0; i < n; i++) {
    const d = new Date(today);
    d.setDate(today.getDate() + i);
    dates.push(dateToString(d));
  }
  return dates;
}

export function formatDateChip(dateString: string): string {
  const d = new Date(`${dateString}T00:00:00`);
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit", weekday: "short" });
}

export function formatSlotTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" });
}
