import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import AuthPage from "./AuthPage";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

describe("authentication before hydration", () => {
  it.each([false, true])(
    "never exposes credentials through a native GET form (register=%s)",
    (register) => {
      const html = renderToStaticMarkup(<AuthPage register={register} />);
      expect(html).toMatch(/<form[^>]+method="post"/);
      expect(html).toMatch(/<button(?=[^>]*type="submit")(?=[^>]*disabled="")[^>]*>/);
      expect(html).not.toMatch(/method="get"/);
    },
  );
});
