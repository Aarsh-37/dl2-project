import { test, expect } from "@playwright/test";

// Smoke: upload -> stream -> ATS -> approve (tasks.md eval).
// Runs live against the backend (uvicorn app.main:app --port 8010).

test("upload → ATS visible → approve", async ({ page }) => {
  await page.goto("/analyze");
  await expect(page.getByText("Upload resume")).toBeVisible();
  await page.getByPlaceholder(/Paste the JD/i).fill(
    "We are hiring a Backend Developer with React, Node.js, Python, AWS and Docker experience. ".repeat(3)
  );
  await page.getByRole("button", { name: /analyze/i }).click();
  await expect(page).toHaveURL(/\/results\//, { timeout: 10000 });
  await expect(page.getByText("AI Career Analysis")).toBeVisible();
  await expect(page.getByText(/Top-3 quick wins|ATS engine/i).first()).toBeVisible({ timeout: 15000 });
});
