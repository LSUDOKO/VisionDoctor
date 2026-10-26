import { expect, test } from "@playwright/test";

test("landing, fleet, incidents and traces render", async ({ page }) => {
  await page.goto("/#/about");
  await expect(page.getByRole("heading", { level: 1, name: /watches the cameras/ })).toBeVisible();

  await page.getByTestId("landing-cta").click();
  // auth-enabled deployments land on the sign-in screen; local demo goes straight to the console
  const login = page.getByTestId("login-screen");
  const tile = page.getByTestId("camera-tile").first();
  await expect(login.or(tile)).toBeVisible({ timeout: 45_000 });
  if (await login.isVisible()) return;

  await expect(page.getByRole("heading", { name: "Fleet" })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Console" });
  await nav.getByRole("link", { name: /Incidents/ }).click();
  await expect(page.getByRole("heading", { name: "Incident queue" })).toBeVisible();

  await nav.getByRole("link", { name: /Traces/ }).click();
  await expect(page.getByRole("heading", { name: "Agent traces" })).toBeVisible();
});
