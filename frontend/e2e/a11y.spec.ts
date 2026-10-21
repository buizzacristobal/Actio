import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

// @axe-core/playwright bundles its own playwright-core types; the cast bridges the duplicate declarations.
const axe = (page: Page) => new AxeBuilder({ page: page as never });

for (const path of ["/", "/privacidad", "/app"]) {
  test(`axe: no serious or critical violations on ${path}`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" }); // axe must not sample colors mid-transition
    await page.goto(path);
    const { violations } = await axe(page).analyze();
    const bad = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`)).toEqual([]);
  });
}

test("axe on the review and ledger steps", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/app");
  await page.getByRole("button", { name: "Pagaré", exact: true }).click();
  for (const heading of ["2. Revisión de datos extraídos", "2. Liquidación de la deuda"]) {
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    const { violations } = await axe(page).analyze();
    expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);
    await page.getByRole("button", { name: /Continuar/ }).click();
  }
});

test.describe("mobile", () => {
  test.use({ viewport: { width: 390, height: 844 } });
  for (const path of ["/", "/app"]) {
    test(`no horizontal overflow on ${path}`, async ({ page }) => {
      await page.goto(path);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
  }
});
