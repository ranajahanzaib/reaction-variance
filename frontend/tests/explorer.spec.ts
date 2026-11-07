import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
test("real dataset: browse, filter, compare, export and methodology", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/*", (route) =>
    new URL(route.request().url()).hostname === "127.0.0.1"
      ? route.continue()
      : route.abort(),
  );
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "A shared chemical starting point" }),
  ).toBeVisible();
  await expect(page.getByRole("checkbox")).toHaveCount(25);
  await expect(
    page.getByRole("img", { name: /Molecular structure/ }),
  ).toHaveCount(3);
  await page.locator(".group-card").nth(1).click();
  await expect(page.locator(".stats").getByText("13,824")).toBeVisible();
  await page.locator(".group-card").nth(0).click();
  await expect(page.locator(".stats").getByText("3,072")).toBeVisible();
  const baseline = await page.locator(".chart-summary").innerText();
  const filter = page.getByLabel("Filter temperature");
  await filter.selectOption({ index: 1 });
  await expect(page.locator(".chart-summary")).not.toHaveText(baseline);
  await expect(page.locator(".chart-summary")).not.toContainText("Loading");
  await expect(page.getByRole("checkbox")).toHaveCount(25);
  await page.getByLabel("Minimum yield").fill("100");
  await page.getByLabel("Maximum yield").fill("100");
  await expect(page.locator(".chart-summary")).toContainText(
    "0 filtered experiments",
  );
  await expect(
    page.getByText("No experiments match these filters."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reset", exact: true }).click();
  await expect(page.getByRole("checkbox")).toHaveCount(25);
  await page.getByRole("checkbox").nth(0).check();
  await page.getByRole("checkbox").nth(1).check();
  await expect(page.locator(".comparison-yields")).toBeVisible();
  await expect(page.locator(".difference-matrix tbody tr")).toHaveCount(11);
  await expect(page.locator(".interpretation")).toContainText("not causes");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export comparison" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("reactionvariance-comparison.csv");
  const path = await download.path();
  const csv = await readFile(path!, "utf8");
  expect(csv).toContain("CC-BY-SA-4.0");
  expect(csv.split("\n").filter(Boolean)).toHaveLength(3);
  await page.locator(".candidate-panel").scrollIntoViewIfNeeded();
  await expect(page.locator(".candidates button").first()).toBeVisible();
  await page.locator(".candidates button").first().click();
  await expect(page.locator(".delta b")).toHaveText("single recorded factor");
  await expect(page.locator(".difference-matrix .differ")).toHaveCount(1);
  await page.locator("#comparison").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `../docs/comparison-${info.project.name}.png`,
  });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `../docs/explorer-${info.project.name}.png` });
  const width = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    viewport: innerWidth,
  }));
  expect(width.scroll).toBeLessThanOrEqual(width.viewport);
  const exploreAccess = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    exploreAccess.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  ).toEqual([]);
  await page
    .getByRole("button", { name: "Data & methodology", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Transparent by construction." }),
  ).toBeVisible();
  await expect(page.getByText("50,688 / 4 / 50,668")).toBeVisible();
  expect(errors).toEqual([]);
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    accessibility.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  ).toEqual([]);
});
