import { test, expect } from "@playwright/test";

test("recorded viewer keeps decisions scoped and audit independent", async ({
  page,
}) => {
  await page.goto("http://127.0.0.1:4173");
  await expect(
    page.getByRole("heading", { name: "How many more should we reopen?" }),
  ).toBeVisible();
  await page.locator(".queueitem").first().click();
  await page.getByRole("button", { name: /Missed pedestrian/ }).click();
  await expect(
    page.getByText("Saved locally: Missed pedestrian"),
  ).toBeVisible();
  await page.getByRole("button", { name: /Out of scope/ }).click();
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(
    page.getByText("Saved locally: Missed pedestrian"),
  ).toBeVisible();
  const events = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("avtriage-decisions") || "[]"),
  );
  expect(events[2].supersedes).toBe(events[1].id);
  await page.getByRole("button", { name: "Audit", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Fixed sample, full-frame inspection" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Investigation", exact: true })
    .click();
  await page.getByLabel("Seed").selectOption("1");
  await expect(page.getByText("Saved locally: Missed pedestrian")).toHaveCount(
    0,
  );
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "How many more should we reopen?" }),
  ).toBeVisible();
});
