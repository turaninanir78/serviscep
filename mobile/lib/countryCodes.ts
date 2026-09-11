// Web'in frontend/lib/countryCodes.ts dosyasiyla ayni liste, ayri client.
// Su an sadece Turkiye destekleniyor (backend de sadece "+90" kabul ediyor -
// bkz. backend/app/phone.py::SUPPORTED_COUNTRY_CODES). Yeni bir ulke eklemek
// SADECE bu listeye bir satir eklemek demek.
export interface CountryCode {
  code: string;
  label: string;
  flag: string;
}

export const COUNTRY_CODES: CountryCode[] = [{ code: "+90", label: "Türkiye", flag: "🇹🇷" }];

export const DEFAULT_COUNTRY_CODE = COUNTRY_CODES[0].code;
