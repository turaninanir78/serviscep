import { describe, expect, test } from "@jest/globals";
import { render } from "@testing-library/react-native";

import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  test.each([
    ["pending", "Beklemede"],
    ["confirmed", "Onaylandı"],
    ["cancelled", "İptal Edildi"],
    ["completed", "Tamamlandı"],
    ["no_show", "Gelmedi"],
  ])("status=%s için '%s' etiketini gösterir", (status: string, label: string) => {
    const { getByText } = render(<StatusBadge status={status} />);
    expect(getByText(label)).toBeTruthy();
  });

  test("bilinmeyen bir status için ham değeri gösterir", () => {
    const { getByText } = render(<StatusBadge status="weird_status" />);
    expect(getByText("weird_status")).toBeTruthy();
  });
});
