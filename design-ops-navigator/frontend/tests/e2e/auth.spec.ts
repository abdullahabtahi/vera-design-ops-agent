import { test, expect } from "@playwright/test";

/**
 * Auth page smoke tests.
 * These run against the Next.js dev server (no Firebase credentials needed —
 * they test the UI shell, redirects, and static content only).
 */

test.describe("Auth page redesign", () => {
  test("renders Get Started heading and Google button", async ({ page }) => {
    await page.goto("/auth");
    await expect(page.getByRole("heading", { name: "Get Started" })).toBeVisible();
    await expect(page.getByText("Continue with Google")).toBeVisible();
  });

  test("shows expert UX critique headline", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/auth");
    // h1 is in the left panel — visible at desktop viewport
    await expect(page.locator("h1")).toContainText("Expert UX Critique");
  });

  test("reveals email form on toggle", async ({ page }) => {
    await page.goto("/auth");
    // Find and click the email toggle button
    const allButtons = page.locator("button");
    for (let i = 0; i < await allButtons.count(); i++) {
      const text = await allButtons.nth(i).textContent();
      if (text && text.includes("email")) {
        await allButtons.nth(i).click();
        break;
      }
    }
    // Target the email input field in the sign-in form (use role to avoid ambiguity)
    await expect(page.getByRole("textbox", { name: "Email", exact: true })).toBeVisible();
    await expect(page.getByPlaceholder("Password")).toBeVisible();
  });

  test("back button returns to Google sign-in", async ({ page }) => {
    await page.goto("/auth");
    await page.getByText("Sign in with email credentials →").click();
    await page.getByRole("button", { name: /← Back to Google/ }).click();
    // The password field should be hidden after clicking back
    await expect(page.getByPlaceholder("Password")).not.toBeVisible();
  });

  test("waitlist form accepts valid email", async ({ page }) => {
    await page.goto("/auth");
    // Scroll or find the waitlist input in the bottom card
    const waitlistInput = page.getByPlaceholder("your@email.com").first();
    await waitlistInput.fill("test@example.com");
    // Verify the input was filled
    await expect(waitlistInput).toHaveValue("test@example.com");
  });

  test("displays feature list in left panel", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/auth");
    // Left panel feature items — visible at desktop viewport
    await expect(page.getByText("Figma & live website critique")).toBeVisible();
    await expect(page.getByText("Severity scoring and issue tracking")).toBeVisible();
    await expect(page.getByText("Design system context awareness")).toBeVisible();
  });
});

test.describe("Middleware redirect", () => {
  test("unauthenticated user is redirected to /auth from /", async ({ page }) => {
    // Clear all cookies to simulate unauthenticated state
    await page.context().clearCookies();
    await page.goto("/");
    await expect(page).toHaveURL(/\/auth/);
  });

  test("unauthenticated user is redirected to /auth from /knowledge", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto("/knowledge");
    await expect(page).toHaveURL(/\/auth/);
  });

  test("unauthenticated user is redirected to /auth from /history", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto("/history");
    await expect(page).toHaveURL(/\/auth/);
  });
});
