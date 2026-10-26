import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { parse } from "node:path";
import { chromium, expect } from "../../frontend/node_modules/@playwright/test/index.mjs";

const base = process.env.APF_WEB_URL;
if (!base) throw new Error("Set APF_WEB_URL to an isolated AstroPhotoFlow workspace URL.");
const origin = new URL(base).origin;
const report = new URL("../../.artifacts/reports/native-web/", import.meta.url);
await mkdir(report, { recursive: true });
const image = await readFile(new URL("../fixtures/native-web.png", import.meta.url));
const name = `native-web-${Date.now()}.png`;
const assetName = parse(name).name;
const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
});
const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    locale: "zh-CN",
    extraHTTPHeaders: { Origin: origin },
});
const page = await context.newPage();
const errors = [];
const remote = [];
const checks = [];
page.on("pageerror", (error) => errors.push(String(error)));
await context.route("**/*", (route) => {
    const url = route.request().url();
    if (url.startsWith("http") && new URL(url).origin !== origin) {
        remote.push(url);
        return route.abort();
    }
    return route.continue();
});

async function navigate(destination) {
    if (destination === "equipment") {
        await page.getByRole("button", { name: "设备管理", exact: true }).click();
    } else {
        await page.locator(`[data-testid="native-navigation"] a[href^="#/${destination}"]`).click();
    }
    await expect(page).toHaveURL(new RegExp(`#/${destination}(\\?.*)?$`));
}

try {
    await page.goto(origin, { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/#\/library$/);
    await expect(
        page.getByTestId("native-navigation").getByRole("link", { name: "素材库", exact: true }),
    ).toBeVisible();
    await expect(page.locator("#graph-canvas")).toHaveCount(0);
    const health = await page.request.get(origin + "/astrophotoflow/api/v1/health");
    assert.equal(health.status(), 200);
    assert.equal((await health.json()).schema_revision, "0009_remove_legacy_capture_profiles");
    assert.ok(health.headers()["x-request-id"]);
    assert.equal(health.headers().authorization, undefined);
    checks.push("native default page and authenticated gateway");

    await page.setViewportSize({ width: 414, height: 1000 });
    const navBounds = await page.getByTestId("native-navigation").boundingBox();
    assert.ok(navBounds.x < 64 && navBounds.width <= 64);
    await expect(page.getByRole("button", { name: "设备管理", exact: true })).toBeInViewport();
    await expect(page.getByRole("button", { name: "导入", exact: true })).toBeInViewport();
    await expect(page.getByTestId("native-navigation").getByRole("link")).toHaveCount(2);
    await page.screenshot({
        path: fileURLToPath(new URL("navigation-narrow.png", report)),
        fullPage: true,
    });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await navigate("equipment");
    await expect(page.getByRole("heading", { name: "设备管理", exact: true })).toBeVisible();
    await expect(page.locator(".apf-management-tabs button[aria-current='page']")).toHaveText(
        "设备",
    );
    await page
        .locator(".apf-management-tabs")
        .getByRole("button", { name: "项目", exact: true })
        .click();
    await page.getByRole("button", { name: "新建项目", exact: true }).click();
    const editor = page.getByRole("region", { name: "记录编辑表单" });
    await editor.getByLabel("名称", { exact: true }).fill(name);
    await editor.getByRole("button", { name: "保存", exact: true }).click();
    await expect(page.getByText(name, { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "新建项目", exact: true }).click();
    await editor.getByLabel("名称", { exact: true }).fill("unsaved native draft");
    page.once("dialog", (dialog) => dialog.dismiss());
    await page.locator('[data-testid="native-navigation"] a[href^="#/library"]').click();
    await expect(page).toHaveURL(/#\/equipment$/);
    await expect(editor.getByLabel("名称", { exact: true })).toHaveValue("unsaved native draft");
    page.once("dialog", (dialog) => dialog.accept());
    await navigate("workflows");
    await expect(page.getByTestId("side-toolbar")).toBeVisible({ timeout: 45000 });
    const toolsBounds = await page.getByTestId("side-toolbar").boundingBox();
    assert.ok(toolsBounds.x < 64 && toolsBounds.width <= 64);
    const mainBounds = await page.locator("#graph-canvas-container").boundingBox();
    assert.ok(mainBounds.x >= 64);
    checks.push("project creation and draft navigation protection");

    const uploaded = await page.request.post(origin + "/api/upload/image", {
        multipart: { image: { name, mimeType: "image/png", buffer: image } },
    });
    assert.equal(uploaded.status(), 200);
    const sourceName = (await uploaded.json()).name;
    await page.evaluate(() => window.app.reloadNodeDefs());
    const draft = await page.evaluate((sourceName) => {
        const app = window.app;
        const input = window.LiteGraph.createNode("LoadImage");
        input.title = "Native input";
        input.widgets.find((widget) => widget.name === "image").value = sourceName;
        input.pos = [460, 160];
        app.graph.add(input);
        const output = window.LiteGraph.createNode("SaveImage");
        output.title = "Native output";
        output.widgets.find((widget) => widget.name === "filename_prefix").value =
            "APF-native-validation";
        output.pos = [820, 160];
        app.graph.add(output);
        input.connect(0, output, 0);
        app.canvas.ds.scale = 0.8;
        app.canvas.ds.offset = [34, 56];
        app.canvas.setDirty(true, true);
        return {
            nodes: app.graph.serialize().nodes.map((node) => ({ id: node.id, title: node.title })),
            scale: app.canvas.ds.scale,
            offset: Array.from(app.canvas.ds.offset),
        };
    }, sourceName);
    await navigate("library");
    await navigate("equipment");
    await navigate("workflows");
    const retained = await page.evaluate(() => ({
        nodes: window.app.graph
            .serialize()
            .nodes.map((node) => ({ id: node.id, title: node.title })),
        scale: window.app.canvas.ds.scale,
        offset: Array.from(window.app.canvas.ds.offset),
    }));
    assert.deepEqual(retained, draft);
    const graph = await page.evaluate(() => window.app.graph.serialize());
    const savedPath = `workflows/${name}.json`;
    const saved = await page.request.post(
        origin + "/api/userdata/" + encodeURIComponent(savedPath),
        { data: graph },
    );
    assert.equal(saved.status(), 200);
    const loaded = await page.request.get(
        origin + "/api/userdata/" + encodeURIComponent(savedPath),
    );
    assert.equal(loaded.status(), 200);
    await page.evaluate(async (graph) => window.app.loadGraphData(graph), await loaded.json());
    assert.equal(await page.evaluate(() => window.app.graph.serialize().nodes.length), 2);
    const receipt = await page.evaluate(async () =>
        window.comfyAPI.api.api.queuePrompt(0, await window.app.graphToPrompt()),
    );
    await expect
        .poll(
            async () => {
                const response = await page.request.get(
                    origin + "/api/history/" + receipt.prompt_id,
                );
                return (await response.json())[receipt.prompt_id]?.status?.completed;
            },
            { timeout: 30000 },
        )
        .toBe(true);
    await page.screenshot({
        path: fileURLToPath(new URL("workflows.png", report)),
        fullPage: true,
    });
    checks.push("graph and viewport retention, workflow save/load, actual CPU queue execution");

    await navigate("library");
    await page
        .locator('input[type="file"]')
        .first()
        .setInputFiles({ name, mimeType: "image/png", buffer: image });
    await page
        .getByRole("dialog", { name: "导入天文素材" })
        .getByRole("button", { name: "开始导入", exact: true })
        .click();
    const row = page.getByRole("row").filter({ hasText: assetName });
    await expect(row.locator(".apf-thumb img")).toBeVisible({ timeout: 30000 });
    await row.getByRole("button", { name: `查看 ${assetName} 大图`, exact: true }).click();
    const preview = page.getByRole("dialog", { name: `${assetName} 大图预览`, exact: true });
    await expect(preview.locator("img")).toBeVisible({ timeout: 30000 });
    await preview.getByRole("button", { name: "关闭大图预览", exact: true }).click();
    checks.push("browser upload, thumbnail and automatic display preview");

    const api = origin + "/astrophotoflow/api/v1";
    const assets = await (
        await page.request.get(api + "/library/assets?q=" + encodeURIComponent(assetName))
    ).json();
    const asset = assets.items.find((item) => item.name === assetName);
    assert.ok(asset);
    const removed = await page.request.delete(api + "/library/items", {
        data: {
            items: [
                {
                    entry_type: "asset",
                    id: asset.id,
                    revision: asset.revision,
                    current_version_id: asset.current_version_id,
                },
            ],
        },
    });
    assert.equal(removed.status(), 200);
    const trash = await (await page.request.get(api + "/library/trash")).json();
    const item = trash.items.find((item) => item.id === asset.id && item.entry_type === "asset");
    assert.ok(item);
    const selection = Object.fromEntries(
        ["entry_type", "id", "removed_at", "revision", "current_version_id"].map((key) => [
            key,
            item[key],
        ]),
    );
    const restored = await page.request.post(api + "/library/trash/restore", {
        data: { items: [selection] },
    });
    assert.equal(restored.status(), 200);
    await page.getByRole("button", { name: "刷新", exact: true }).click();
    await expect(row).toBeVisible();
    assert.deepEqual(await readFile(new URL("../fixtures/native-web.png", import.meta.url)), image);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(row).toBeVisible();
    await page.screenshot({ path: fileURLToPath(new URL("library.png", report)), fullPage: true });
    checks.push("trash restore, original-byte protection and hash-route reload");
    assert.deepEqual(errors, []);
    assert.deepEqual(remote, []);
} finally {
    await writeFile(new URL("page.txt", report), await page.locator("body").innerText());
    await writeFile(
        new URL("results.json", report),
        JSON.stringify({ checks, errors, remote, url: page.url() }, null, 2),
    );
    await browser.close();
}
console.log(JSON.stringify({ passed: checks.length, checks }, null, 2));
