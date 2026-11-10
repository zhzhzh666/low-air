import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(String.raw`C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1105-1297-0_26.1105.1297.0_x64__3k8sg7r9htsxt\dependencies\node\node_modules\playwright`);

const root = String.raw`C:\Users\zh\Desktop\git\低空物流系统`;
const outputDir = path.join(root, "video_output");
const browserPath = String.raw`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`;
const finalWebm = path.join(outputDir, "SZU_粤海车机协同_强风滚动规划_仿真回放.webm");

await fs.mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  executablePath: browserPath,
  args: [
    "--use-angle=swiftshader",
    "--enable-webgl",
    "--ignore-gpu-blocklist",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
  ],
});

const context = await browser.newContext({
  viewport: { width: 1600, height: 900 },
  deviceScaleFactor: 1,
});

const page = await context.newPage();
const outputHandle = await fs.open(finalWebm, "w");
await page.exposeFunction("saveVideoChunk", async (base64) => {
  await outputHandle.write(Buffer.from(base64, "base64"));
});

await page.goto("http://127.0.0.1:8765/index.html?speed=300", { waitUntil: "networkidle" });
await page.waitForFunction(() => document.querySelector("#case-label")?.textContent?.includes("突发强风"));

await page.locator('[data-case="gust_milp"]').click();
if ((await page.locator("#play-button").textContent())?.includes("暂停")) {
  await page.locator("#play-button").click();
}
await page.locator("#timeline").evaluate((element) => {
  element.value = "0";
  element.dispatchEvent(new Event("input", { bubbles: true }));
});

await page.evaluate(async () => {
  const width = 1600;
  const height = 900;
  const sidebarX = 1220;
  const titleDuration = 2600;
  const totalDuration = 38100;
  const source = document.querySelector("#map-canvas");
  const output = document.createElement("canvas");
  output.width = width;
  output.height = height;
  const ctx = output.getContext("2d");
  const stream = output.captureStream(30);
  const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9")
    ? "video/webm;codecs=vp9"
    : "video/webm;codecs=vp8";
  const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 8_000_000 });
  let writeChain = Promise.resolve();
  const toBase64 = async (blob) => {
    const bytes = new Uint8Array(await blob.arrayBuffer());
    let binary = "";
    for (let i = 0; i < bytes.length; i += 0x8000) {
      binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    }
    return btoa(binary);
  };
  recorder.addEventListener("dataavailable", (event) => {
    if (!event.data.size) return;
    writeChain = writeChain.then(async () => window.saveVideoChunk(await toBase64(event.data)));
  });

  const text = (value, x, y, size, color = "#f4fbff", weight = 400, align = "left") => {
    ctx.font = `${weight} ${size}px "Microsoft YaHei", "Segoe UI", sans-serif`;
    ctx.fillStyle = color;
    ctx.textAlign = align;
    ctx.textBaseline = "top";
    ctx.fillText(String(value), x, y);
  };
  const wrap = (value, x, y, maxWidth, lineHeight, size, color = "#9bb2bc", weight = 400) => {
    ctx.font = `${weight} ${size}px "Microsoft YaHei", "Segoe UI", sans-serif`;
    ctx.fillStyle = color;
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    let line = "";
    let yy = y;
    for (const char of String(value)) {
      const test = line + char;
      if (ctx.measureText(test).width > maxWidth && line) {
        ctx.fillText(line, x, yy);
        line = char;
        yy += lineHeight;
      } else {
        line = test;
      }
    }
    if (line) ctx.fillText(line, x, yy);
  };
  const roundRect = (x, y, w, h, r, fill, stroke = null) => {
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, r);
    ctx.fillStyle = fill;
    ctx.fill();
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  };
  const metric = (label, value, unit, x, y) => {
    roundRect(x, y, 156, 92, 10, "#102b37", "#20424f");
    text(label, x + 14, y + 12, 15, "#8fa9b3");
    text(value, x + 14, y + 42, 27, "#f4fbff", 700);
    if (unit) text(unit, x + 135, y + 58, 12, "#8fa9b3", 400, "right");
  };
  const drawMap = () => {
    const sw = source.width || 1;
    const sh = source.height || 1;
    const scale = Math.max(sidebarX / sw, height / sh);
    const cropW = sidebarX / scale;
    const cropH = height / scale;
    ctx.drawImage(source, (sw - cropW) / 2, (sh - cropH) / 2, cropW, cropH, 0, 0, sidebarX, height);
    const gradient = ctx.createLinearGradient(0, 0, 0, 150);
    gradient.addColorStop(0, "rgba(2,11,16,.90)");
    gradient.addColorStop(1, "rgba(2,11,16,0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, sidebarX, 150);
    text("深圳大学粤海校区车机协同取件仿真", 38, 28, 30, "#f4fbff", 700);
    text(document.querySelector("#case-label")?.textContent || "突发强风 · 滚动整数规划", 40, 74, 19, "#9eea45", 600);
    text(document.querySelector("#sim-clock")?.textContent || "T+00:00:00", sidebarX - 36, 34, 22, "#f4fbff", 600, "right");
  };
  const drawSidebar = () => {
    ctx.fillStyle = "#071923";
    ctx.fillRect(sidebarX, 0, width - sidebarX, height);
    text("MISSION CONTROL", sidebarX + 28, 28, 15, "#9eea45", 700);
    text("节点天气与电池闭环", sidebarX + 28, 58, 24, "#f4fbff", 700);
    metric("剩余电量", document.querySelector("#battery-value")?.textContent || "756.00", "Wh", sidebarX + 28, 112);
    metric("20% 安全阈值", "151.20", "Wh", sidebarX + 196, 112);
    metric("节点观测风速", document.querySelector("#wind-value")?.textContent || "0.00", "m/s", sidebarX + 28, 216);
    metric("来风方向", document.querySelector("#wind-direction")?.textContent || "静风", "", sidebarX + 196, 216);
    metric("卡车里程", document.querySelector("#distance-value")?.textContent || "0.00", "km", sidebarX + 28, 320);
    metric("换电次数", document.querySelector("#swap-value")?.textContent || "0", "次", sidebarX + 196, 320);
    roundRect(sidebarX + 28, 430, 324, 108, 12, "#0d2530", "#20424f");
    text("可规划使用电量", sidebarX + 46, 448, 15, "#8fa9b3");
    text(document.querySelector("#available-value")?.textContent || "604.80 Wh", sidebarX + 46, 477, 27, "#9eea45", 700);
    roundRect(sidebarX + 46, 516, 286, 8, 4, "#263f49");
    const battery = Math.max(0, Math.min(100, Number(document.querySelector("#battery-value")?.textContent || 756) / 756 * 100));
    roundRect(sidebarX + 46, 516, 286 * battery / 100, 8, 4, battery <= 20 ? "#f28a54" : "#9eea45");
    roundRect(sidebarX + 28, 558, 324, 224, 12, "#0d2530", "#20424f");
    text("决策日志", sidebarX + 46, 578, 15, "#8fa9b3");
    wrap(document.querySelector("#decision-title")?.textContent || "读取天气与车辆状态", sidebarX + 46, 610, 286, 29, 22, "#f4fbff", 700);
    wrap(document.querySelector("#decision-detail")?.textContent || "", sidebarX + 46, 676, 286, 24, 16, "#9bb2bc");
    const progress = Number(document.querySelector("#timeline")?.value || 0) / 1000;
    ctx.fillStyle = "#173441";
    ctx.fillRect(sidebarX + 28, 832, 324, 8);
    ctx.fillStyle = "#56b4df";
    ctx.fillRect(sidebarX + 28, 832, 324 * progress, 8);
    text("八方向风场 · 航段风速不超过 14 m/s", sidebarX + 28, 856, 14, "#7d99a4");
  };

  const startedAt = performance.now();
  let playbackStarted = false;
  const completion = new Promise((resolve, reject) => {
    recorder.addEventListener("error", reject, { once: true });
    recorder.addEventListener("stop", () => writeChain.then(resolve, reject), { once: true });
  });
  recorder.start(1000);

  const render = (now) => {
    const elapsed = now - startedAt;
    ctx.fillStyle = "#06141c";
    ctx.fillRect(0, 0, width, height);
    if (elapsed < titleDuration) {
      text("深圳大学粤海校区车机协同取件仿真", width / 2, 330, 48, "#f4fbff", 700, "center");
      text("突发强风 · 滚动整数规划", width / 2, 415, 30, "#9eea45", 700, "center");
      text("八方向风场｜节点重判｜20% 电量阈值", width / 2, 472, 20, "#91aab5", 400, "center");
    } else {
      if (!playbackStarted) {
        document.querySelector("#play-button")?.click();
        playbackStarted = true;
      }
      drawMap();
      drawSidebar();
    }
    if (elapsed < totalDuration) requestAnimationFrame(render);
    else recorder.stop();
  };
  requestAnimationFrame(render);
  await completion;
});

await outputHandle.close();

await page.close();
await context.close();
await browser.close();

console.log(finalWebm);
