import { ApiError } from "./api";

const KNOWN_MESSAGES: Record<string, string> = {
  "Invalid email or password": "E-posta veya şifre hatalı.",
  "Email already registered": "Bu e-posta adresi zaten kayıtlı.",
};

export function describeApiError(err: unknown): string {
  if (err instanceof ApiError) {
    return KNOWN_MESSAGES[err.message] ?? err.message;
  }
  return "Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.";
}
