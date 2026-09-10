import { ApiError } from "./api";

// Backend'in ham "detail" metni kullaniciya asla dogrudan basilmaz - sadece
// bilinen HTTP durum kodlari icin sabit, Turkce mesajlar gosterilir. Web'in
// frontend/lib/errors.ts dosyasiyla ayni sozlesme.
const STATUS_MESSAGES: Record<number, string> = {
  400: "İstek geçersiz. Lütfen bilgileri kontrol edip tekrar deneyin.",
  401: "Giriş bilgileriniz geçersiz veya oturumunuzun süresi dolmuş.",
  403: "Bu işlem için yetkiniz yok.",
  404: "Aradığınız kayıt bulunamadı.",
  409: "Bu işlem mevcut bir kayıtla çakışıyor.",
  422: "Girilen bilgiler geçersiz. Lütfen kontrol edin.",
  429: "Çok fazla deneme yapıldı. Lütfen biraz bekleyip tekrar deneyin.",
};

const FALLBACK_MESSAGE = "Bir şeyler ters gitti, tekrar deneyin.";

export function describeApiError(err: unknown): string {
  if (err instanceof ApiError) {
    return STATUS_MESSAGES[err.status] ?? FALLBACK_MESSAGE;
  }
  return FALLBACK_MESSAGE;
}
