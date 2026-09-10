// Backend, musaitlik/randevu saatlerini TENANT saat diliminde uretiyor (bkz.
// backend/app/core/availability.py - ZoneInfo(tenant.timezone)) ve ISO
// string'lerde tenant'in offset'ini tasiyan mutlak anlar (instant) donuyor.
// Bu dosyadaki her fonksiyon, goruntulemeyi VE "bugun"/"sonraki N gun" gibi
// slot sorgusu icin kullanilan tarih hesaplarini CIHAZIN yerel saat dilimi
// yerine acikca TENANT saat dilimiyle yapiyor - aksi halde farkli bir
// ulkedeki/saat diliminde bir cihazdan bakan kullanici gun sinirina yakin
// randevularda yanlis gun/saat gorebilir (iki kullanici ayni anda farkli
// "bugun"e sahip olabilir).

function formatInTimezone(date: Date, timezone: string): string {
  // en-CA locale'inin varsayilan tarih formati ISO (YYYY-MM-DD) oldugu icin
  // manuel offset hesabi yapmadan, DST dahil butun kurallari Intl'e
  // birakarak guvenilir bir "bu an, su saat diliminde hangi takvim gunu"
  // sonucu aliyoruz.
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

export function todayDateString(timezone: string): string {
  return formatInTimezone(new Date(), timezone);
}

// Bir randevunun start_at'i (mutlak an) gibi bir ISO string'in, tenant'in
// takviminde hangi gune denk geldigini dondurur (ornegin yeniden planlama
// formunun baslangic tarihini doldurmak icin).
export function dateStringInTimezone(iso: string, timezone: string): string {
  return formatInTimezone(new Date(iso), timezone);
}

// Salt "YYYY-MM-DD" bir tarihe N gun ekler. Kasitli olarak UTC-ankraji
// kullanir (gercek bir saat dilimine degil) - burada amac sadece takvim
// gunu aritmetigi, gercek bir ana donusum degil; bu sayede DST gibi
// karisikliklardan tamamen bagimsiz kalir.
function addCalendarDays(dateString: string, days: number): string {
  const base = new Date(`${dateString}T00:00:00Z`);
  const shifted = new Date(base.getTime() + days * 24 * 60 * 60 * 1000);
  return formatInTimezone(shifted, "UTC");
}

// Yerlesik bir takvim/date-picker widget'i yerine (native modul + Expo Go
// uyumluluk riski), yeniden planlama ve yeni randevu icin basit,
// platformdan bagimsiz bir "sonraki N gun" secici kullaniliyor.
export function nextNDates(n: number, timezone: string): string[] {
  const today = todayDateString(timezone);
  const dates: string[] = [];
  for (let i = 0; i < n; i++) {
    dates.push(addCalendarDays(today, i));
  }
  return dates;
}

// Girdi zaten tenant saat dilimine gore hesaplanmis salt bir "YYYY-MM-DD"
// oldugu icin (bkz. nextNDates), burada tekrar tenant saat dilimine
// cevirmeye gerek yok - sadece cihazin yerel saat diliminin bu ISO string'i
// YANLIS bir takvim gunune yuvarlamasini onlemek icin UTC'ye ankorlanip
// UTC olarak formatlaniyor.
export function formatDateChip(dateString: string): string {
  const d = new Date(`${dateString}T00:00:00Z`);
  return new Intl.DateTimeFormat("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    weekday: "short",
    timeZone: "UTC",
  }).format(d);
}

export function formatSlotTime(iso: string, timezone: string): string {
  return new Date(iso).toLocaleTimeString("tr-TR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: timezone,
  });
}

export function formatDateTime(iso: string, timezone: string): string {
  return new Date(iso).toLocaleString("tr-TR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: timezone,
  });
}
