import { expect, test } from "@playwright/test";
import samples from "../src/lib/samples.json";

test("full flow: sample → review → ledger → preview → .docx", async ({ page }) => {
  await page.goto("/app");
  await page.getByRole("button", { name: "Pagaré", exact: true }).click();

  // Review step: an invalid RUT blocks continuing
  await expect(page.getByRole("heading", { name: "2. Revisión de datos extraídos" })).toBeVisible();
  const rut = page.getByLabel("RUT").first();
  await rut.fill("12.345.678-9");
  await expect(page.getByText("RUT inválido (dígito verificador).")).toBeVisible();
  await expect(page.getByRole("button", { name: /Continuar/ })).toBeDisabled();
  await rut.fill("76.086.428-5");
  await page.getByRole("button", { name: /Continuar/ }).click();

  // Ledger step
  await expect(page.getByRole("heading", { name: "2. Liquidación de la deuda" })).toBeVisible();
  await expect(page.getByText("No reajustable CLP ≤ 50 UF")).toBeVisible();
  await expect(page.getByText("Tablas de tasas NO verificadas")).toBeVisible();
  await page.getByRole("button", { name: /Continuar/ }).click();

  // Lawsuit step: validation, preview, edit, download
  await page.getByRole("button", { name: "Generar vista previa" }).click();
  await expect(page.getByText("Complete nombre y domicilio del abogado.")).toBeVisible();
  await page.getByLabel("Nombre completo").fill("María Soto");
  await page.getByLabel("RUT", { exact: true }).last().fill("11.111.111-9");
  await page.getByLabel("Domicilio").last().fill("Huérfanos 1117, Santiago");
  await page.getByRole("button", { name: "Generar vista previa" }).click();
  await expect(page.getByText("RUT del abogado inválido")).toBeVisible();
  await page.getByLabel("RUT", { exact: true }).last().fill("11.111.111-1");
  await page.getByLabel(/Bienes a embargar/).fill("Vehículo PPU ABCD12");
  await page.getByRole("button", { name: "Generar vista previa" }).click();
  await expect(page.getByText("Notas para el abogado")).toBeVisible();
  const paper = page.getByLabel("Vista previa editable del escrito");
  await expect(paper.locator("textarea").filter({ hasText: "Vehículo PPU ABCD12" })).toHaveCount(1);
  const first = paper.locator("textarea").first();
  await first.fill("TEXTO EDITADO POR EL ABOGADO");

  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /Descargar Demanda/ }).click()]);
  expect(dl.suggestedFilename()).toBe("demanda_ejecutiva.docx");
  const path = await dl.path();
  const fs = await import("node:fs");
  const buf = fs.readFileSync(path!);
  expect(buf.subarray(0, 2).toString()).toBe("PK");
  expect(buf.length).toBeGreaterThan(5000);
});

test("abonos reduce the outstanding capital shown", async ({ page }) => {
  await page.goto("/app");
  await page.getByRole("button", { name: "Pagaré", exact: true }).click();
  await page.getByRole("button", { name: /Continuar/ }).click();
  await page.getByRole("button", { name: "Agregar abono" }).click();
  await page.getByLabel("Fecha del abono").fill("2024-06-01");
  await page.getByLabel(/Monto/).fill("500000");
  await page.getByRole("button", { name: "Recalcular" }).click();
  await expect(page.getByText("Capital (saldo)")).toBeVisible();
});

test("an out-of-range abono is rejected with a clear message", async ({ page }) => {
  await page.goto("/app");
  await page.getByRole("button", { name: "Pagaré", exact: true }).click();
  await page.getByRole("button", { name: /Continuar/ }).click();
  await page.getByRole("button", { name: "Agregar abono" }).click();
  await page.getByLabel("Fecha del abono").fill("2023-01-01");
  await page.getByLabel(/Monto/).fill("1000");
  await page.getByRole("button", { name: "Recalcular" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "debe ser posterior a la emisión" })).toBeVisible();
});

test("extraction failure shows a graceful alert", async ({ page }) => {
  await page.route("**/api/v1/extract", (r) => r.fulfill({ status: 422, json: { detail: "No se pudo extraer un instrumento válido del documento" } }));
  await page.goto("/app");
  await page.getByRole("button", { name: "Ejemplo Pagaré" }).click();
  await page.getByRole("button", { name: "Extraer con IA" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "No se pudo extraer" })).toBeVisible();
});

test("file upload flags fields the extractor did not find", async ({ page }) => {
  await page.route("**/api/v1/extract-file", (r) =>
    r.fulfill({ status: 200, json: { instrument: { ...samples.pagare, jurisdiction: null }, missing_fields: ["jurisdiction"] } }));
  await page.goto("/app");
  await page.getByLabel("Subir documento").setInputFiles({ name: "pagare.png", mimeType: "image/png", buffer: Buffer.from("x") });
  await expect(page.getByRole("heading", { name: "2. Revisión de datos extraídos" })).toBeVisible();
  await expect(page.getByText("Revisar").first()).toBeVisible();
});

test("drafts are saved locally and can be restored", async ({ page }) => {
  await page.goto("/app");
  await page.getByRole("button", { name: "Pagaré", exact: true }).click();
  await page.getByRole("button", { name: /Guardar borrador/ }).click();
  await expect(page.getByRole("status")).toContainText("solo en este navegador");
  await page.goto("/app");
  await expect(page.getByText("Hay un borrador guardado")).toBeVisible();
  await page.getByRole("button", { name: "Restaurar" }).click();
  await expect(page.getByRole("heading", { name: "2. Liquidación de la deuda" })).toBeVisible();
});
