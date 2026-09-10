// Backend, musaitlik/randevu saatlerini TENANT saat diliminde uretiyor (bkz.
// backend/app/core/availability.py - ZoneInfo(tenant.timezone)) ve ISO
// string'lerde tenant'in offset'ini tasiyan mutlak anlar (instant) donuyor.
// Bu dosyadaki her fonksiyon, goruntulemeyi VE "bugun" gibi slot sorgusu
// icin kullanilan tarih hesaplarini TARAYICININ yerel saat dilimi yerine
// acikca TENANT saat dilimiyle yapiyor - aksi halde farkli bir ulkedeki/saat
// diliminde bir tarayicidan bakan kullanici gun sinirina yakin randevularda
// yanlis gun/saat gorebilir. mobile/lib/dates.ts ile paralel (ayni mantik,
// ayri client - React Native'de Intl polyfill'i, web'de native tarayici
// destegi kullaniliyor).

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
