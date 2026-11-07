import { describe, expect, it } from "vitest";
import {
  formatMetric,
  safeExternalUrl,
  errorMessage,
  validateFiles,
} from "./format";
describe("truthful metric presentation", () => {
  it("does not turn missing metrics into a measured zero", () => {
    expect(formatMetric(null)).toBe("暂无数据");
    expect(formatMetric(undefined)).toBe("暂无数据");
    expect(formatMetric(0)).toBe("0");
  });
  it("rejects executable or local links", () => {
    expect(safeExternalUrl("javascript:alert(1)")).toBeNull();
    expect(safeExternalUrl("file:///C:/secret")).toBeNull();
    expect(safeExternalUrl("https://example.com/video")).toBe(
      "https://example.com/video",
    );
  });
  it("preserves server validation details", () => {
    expect(errorMessage({ detail: [{ msg: "密码过短" }] })).toContain(
      "密码过短",
    );
    expect(errorMessage({ error: { message: "预算不足" } })).toBe("预算不足");
  });
  it("rejects an oversize file before upload", () => {
    expect(
      validateFiles([{ name: "clip.mp4", size: 101 * 1024 * 1024 }]),
    ).toContain("100 MB");
    expect(validateFiles([{ name: "demo.png", size: 100 }])).toBeNull();
    expect(validateFiles([{ name: "payload.exe", size: 100 }])).toContain(
      "不支持",
    );
  });
  it("limits cumulative upload size and file count", () => {
    expect(
      validateFiles([
        { name: "one.mp4", size: 60 * 1024 * 1024 },
        { name: "two.mp4", size: 60 * 1024 * 1024 },
      ]),
    ).toContain("100 MB");
    expect(
      validateFiles(
        Array.from({ length: 13 }, () => ({ name: "photo.jpg", size: 100 })),
      ),
    ).toContain("12");
  });
});
