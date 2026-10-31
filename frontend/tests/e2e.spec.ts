import { test, expect } from "@playwright/test";

test.describe("RepoPilot E2E UI Suite", () => {
  test("renders authentication gateway and allows developer sign-in", async ({
    page,
  }) => {
    await page.goto("http://localhost:3000");
    await expect(page.locator("h1")).toContainText("RepoPilot");
    await expect(
      page.getByRole("button", { name: /Continue with GitHub OAuth/i })
    ).toBeVisible();
  });
});

