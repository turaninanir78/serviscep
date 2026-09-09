import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    tsconfigPaths: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    // Tum randevu saatleri tenant'in yerel saatiyle (Turkiye) gosteriliyor
    // (bkz. formatSlotTime -> toLocaleTimeString) - testlerin, testi calistiran
    // makinenin saat dilimine gore kirilgan olmamasi icin sabitleniyor.
    env: {
      TZ: "Europe/Istanbul",
    },
  },
});
