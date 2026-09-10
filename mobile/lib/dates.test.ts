import { afterEach, beforeEach, describe, expect, jest, test } from "@jest/globals";

import {
  dateStringInTimezone,
  formatDateChip,
  formatDateTime,
  formatSlotTime,
  nextNDates,
  todayDateString,
} from "./dates";

describe("lib/dates - tenant saat dilimi", () => {
  beforeEach(() => {
    // 2026-09-10 22:00 UTC: Istanbul'da (UTC+3) zaten 2026-09-11 01:00 -
    // yani "ertesi gun" - ama Los Angeles'ta (Eylul'de UTC-7, PDT) hala
    // 2026-09-10 15:00 - "ayni gun". Bu, gun sinirini gercekten geciyor
    // olmamizi garanti eden bir an.
    jest.useFakeTimers().setSystemTime(new Date("2026-09-10T22:00:00Z"));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test("todayDateString, ayni anda farkli saat dilimleri icin farkli gun dondurur", () => {
    expect(todayDateString("Europe/Istanbul")).toBe("2026-09-11");
    expect(todayDateString("America/Los_Angeles")).toBe("2026-09-10");
  });

  test("nextNDates, tenant saat diliminde 'bugun'den baslar", () => {
    const istanbul = nextNDates(3, "Europe/Istanbul");
    expect(istanbul).toEqual(["2026-09-11", "2026-09-12", "2026-09-13"]);

    const losAngeles = nextNDates(3, "America/Los_Angeles");
    expect(losAngeles).toEqual(["2026-09-10", "2026-09-11", "2026-09-12"]);
  });

  test("formatSlotTime, ayni mutlak ani farkli saat dilimlerinde farkli saat olarak gosterir", () => {
    // 2026-09-14T09:00:00+03:00 = 2026-09-14T06:00:00Z
    const slot = "2026-09-14T09:00:00+03:00";
    expect(formatSlotTime(slot, "Europe/Istanbul")).toBe("09:00");
    // Los Angeles (PDT, UTC-7): 06:00Z -> 23:00 (bir onceki takvim gunu, yerel saat)
    expect(formatSlotTime(slot, "America/Los_Angeles")).toBe("23:00");
  });

  test("formatDateTime, tenant saat dilimini kullanir, cihaz saat dilimini degil", () => {
    const iso = "2026-09-14T09:00:00+03:00";
    const istanbul = formatDateTime(iso, "Europe/Istanbul");
    const losAngeles = formatDateTime(iso, "America/Los_Angeles");
    expect(istanbul).not.toBe(losAngeles);
    expect(istanbul).toContain("09:00");
  });

  test("dateStringInTimezone, bir randevunun mutlak anini tenant takviminde dogru gune cevirir", () => {
    // 2026-09-08T01:00+03:00 (Istanbul yerel) = 2026-09-07T22:00Z - UTC'de
    // "07 Eylul" gorunse de tenant takviminde "08 Eylul"dur.
    const iso = "2026-09-07T22:00:00Z";
    expect(dateStringInTimezone(iso, "Europe/Istanbul")).toBe("2026-09-08");
  });

  test("formatDateChip, cihaz/sistem saat diliminden bagimsiz olarak verilen tarihi gosterir", () => {
    // Girdi zaten tenant saat dilimine gore hesaplanmis salt bir tarih -
    // UTC'ye ankorlandigi icin sistem saati farkli olsa da gun kaymamali.
    expect(formatDateChip("2026-09-14")).toBe("14/09 Pzt");
  });
});
