import { expect, test } from "@playwright/test";

test("fleet, incidents and traces render", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "VisionDoctor" })).toBeVisible();
  await expect(page.getByTestId("camera-tile").first()).toBeVisible({ timeout: 45_000 });

  await page.getByRole("tab", { name: /Incidents/ }).click();
  await expect(page.getByRole("heading", { name: "Incident queue" })).toBeVisible();

  await page.getByRole("tab", { name: /Traces/ }).click();
  await expect(page.getByRole("heading", { name: "Agent traces" })).toBeVisible();
});
