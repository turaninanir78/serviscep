import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// `test: { globals: true }` kullanmiyoruz (vitest'i acikca import ediyoruz),
// bu yuzden @testing-library/react'in otomatik DOM temizligi kendiliginden
// devreye girmiyor - her testten sonra elle cagriliyor, aksi halde ayni
// dosyadaki birbirini izleyen render() cagrilari DOM'da ust uste birikip
// "birden fazla eslesme" hatalarina yol aciyor.
afterEach(() => {
  cleanup();
});
