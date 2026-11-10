import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const WORKSPACE = String.raw`C:\Users\zh\Desktop\git\低空物流系统`;
const BUILD_DIR = path.join(WORKSPACE, "ppt_build_v2");
const OUTPUT_DIR = path.join(WORKSPACE, "ppt_output_v2");
const PREVIEW_DIR = path.join(BUILD_DIR, "report_previews_v6");
const FINAL_PPTX = path.join(OUTPUT_DIR, "SZU_车机协同取件仿真汇报_20261110_v6.pptx");
const SKILL_DIR = String.raw`C:\Users\zh\.codex\plugins\cache\openai-primary-runtime\presentations\26.1105.12137\skills\presentations`;
const RUNTIME_PYTHON = String.raw`C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1105-1297-0_26.1105.1297.0_x64__3k8sg7r9htsxt\dependencies\python\python.exe`;
const RUNTIME_NODE_MODULES = String.raw`C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1105-1297-0_26.1105.1297.0_x64__3k8sg7r9htsxt\dependencies\node\node_modules`;
const TEMPLATE = String.raw`C:\Users\zh\Desktop\建筑PPT模板.pptx`;
process.env.RUNTIME_NODE_MODULES = RUNTIME_NODE_MODULES;
process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES = RUNTIME_NODE_MODULES;

const MEDIA = path.join(BUILD_DIR, "template_extract", "ppt", "media");
const ASSETS = {
  campus: path.join(MEDIA, "image1.png"),
  building: path.join(MEDIA, "image3.jpeg"),
  city: path.join(MEDIA, "image10.jpg"),
  overview: path.join(WORKSPACE, "SZU_Yuehai_Simulation", "overview.png"),
  web3d: path.join(WORKSPACE, "SZU_Yuehai_HTML_Simulation", "three-d-preview.png"),
};

const W = 1600;
const H = 900;
const S = 0.8;
const FONT = "等线";
const FONT_LIGHT = "等线 Light";
const C = {
  blue: "#56B4DF",
  blueDeep: "#176B92",
  blueDark: "#0D4D6C",
  pale: "#EAF6FB",
  pale2: "#F6FBFD",
  ink: "#20313D",
  muted: "#647782",
  line: "#D6E5EC",
  white: "#FFFFFF",
  orange: "#F28A54",
  green: "#4CA56B",
  red: "#D95B5B",
  gray: "#A9B8C0",
};

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

const imageCache = new Map();
async function bytesFor(filePath) {
  if (!imageCache.has(filePath)) {
    const b = await fs.readFile(filePath);
    imageCache.set(filePath, b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
  }
  return imageCache.get(filePath);
}

function addRect(slide, x, y, w, h, fill, opts = {}) {
  return slide.shapes.add({
    geometry: opts.geometry ?? "rect",
    position: { left: x * S, top: y * S, width: w * S, height: h * S, rotation: opts.rotation ?? 0 },
    fill,
    line: opts.line ?? { style: "solid", fill: "none", width: 0 },
    borderRadius: opts.radius,
    shadow: opts.shadow,
    name: opts.name,
  });
}

function addLine(slide, x, y, w, h, color = C.line, width = 2) {
  const normalizedTop = h < 0 ? y + h : y;
  return slide.shapes.add({
    geometry: "line",
    position: { left: x * S, top: normalizedTop * S, width: Math.abs(w) * S, height: Math.abs(h) * S, verticalFlip: h < 0 },
    fill: "none",
    line: { style: "solid", fill: color, width: width * S },
  });
}

function addText(slide, text, x, y, w, h, opts = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left: x * S, top: y * S, width: w * S, height: h * S },
    fill: opts.fill ?? "none",
    line: opts.line ?? { style: "solid", fill: "none", width: 0 },
    borderRadius: opts.radius,
    name: opts.name,
  });
  shape.text = text;
  shape.text.style = {
    typeface: opts.typeface ?? FONT,
    fontSize: (opts.fontSize ?? 24) * S,
    bold: opts.bold ?? false,
    color: opts.color ?? C.ink,
    alignment: opts.align ?? "left",
    verticalAlignment: opts.valign ?? "top",
    lineSpacing: opts.lineSpacing ?? 1.05,
    autoFit: opts.autoFit ?? "shrinkText",
    wrap: "square",
    insets: opts.insets ?? 0,
  };
  return shape;
}

async function addImage(slide, filePath, x, y, w, h, opts = {}) {
  const ext = path.extname(filePath).toLowerCase();
  const contentType = ext === ".png" ? "image/png" : "image/jpeg";
  return slide.images.add({
    blob: await bytesFor(filePath),
    contentType,
    alt: opts.alt ?? "项目图像",
    fit: opts.fit ?? "cover",
    position: { left: x * S, top: y * S, width: w * S, height: h * S },
    geometry: opts.geometry,
    borderRadius: opts.radius,
    crop: opts.crop,
  });
}

function addHeader(slide, no, title, kicker = "") {
  addRect(slide, 0, 0, W, 16, C.blue);
  addRect(slide, 72, 62, 12, 62, C.blue);
  addText(slide, String(no).padStart(2, "0"), 102, 58, 62, 28, {
    fontSize: 19, bold: true, color: C.blueDeep, valign: "middle",
  });
  addText(slide, title, 102, 84, 1120, 52, {
    fontSize: 38, bold: true, typeface: FONT, color: C.ink, valign: "middle",
  });
  if (kicker) addText(slide, kicker, 1230, 88, 300, 34, { fontSize: 17, color: C.muted, align: "right" });
}

function addFooter(slide, page, source = "") {
  addLine(slide, 72, 846, 1456, 0, C.line, 1);
  if (source) addText(slide, source, 72, 856, 1150, 22, { fontSize: 14, color: C.muted });
  addText(slide, String(page).padStart(2, "0"), 1450, 852, 78, 24, {
    fontSize: 15, bold: true, color: C.blueDeep, align: "right",
  });
}

function addMetricCard(slide, value, label, x, y, w, accent = C.blue) {
  addRect(slide, x, y, w, 118, C.white, {
    radius: "rounded-xl", line: { style: "solid", fill: C.line, width: 1 },
  });
  addRect(slide, x, y, 8, 118, accent);
  addText(slide, value, x + 24, y + 20, w - 38, 45, { fontSize: 34, bold: true, color: C.ink });
  addText(slide, label, x + 24, y + 72, w - 38, 26, { fontSize: 18, color: C.muted });
}

function addBullet(slide, title, body, x, y, w, color = C.blue) {
  addRect(slide, x, y + 8, 12, 12, color, { geometry: "ellipse" });
  addText(slide, title, x + 28, y, w - 28, 31, { fontSize: 23, bold: true, color: C.ink });
  addText(slide, body, x + 28, y + 36, w - 28, 56, { fontSize: 20, color: C.muted, lineSpacing: 1.14 });
}

function addNode(slide, label, x, y, color, w = 122) {
  addRect(slide, x, y, w, 62, color, { radius: "rounded-full" });
  return addText(slide, label, x, y, w, 62, {
    fontSize: 22, bold: true, color: C.white, align: "center", valign: "middle",
  });
}

async function build() {
  await fs.mkdir(BUILD_DIR, { recursive: true });
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  await fs.mkdir(PREVIEW_DIR, { recursive: true });

  const presentation = Presentation.create({ slideSize: { width: W * S, height: H * S } });

  // 1. Cover
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.white;
    await addImage(slide, ASSETS.campus, 760, 0, 840, 900, { alt: "深圳大学校园建筑" });
    addRect(slide, 0, 0, 830, 900, C.white);
    addRect(slide, 720, 0, 110, 900, C.blue);
    addRect(slide, 742, 0, 88, 900, C.white, { geometry: "parallelogram" });
    addText(slide, "SHENZHEN UNIVERSITY", 84, 76, 420, 30, {
      fontSize: 17, bold: true, color: C.blueDeep,
    });
    addLine(slide, 84, 128, 184, 0, C.blue, 4);
    addText(slide, "有限天气信息下的\n车机协同取件仿真", 84, 232, 610, 196, {
      fontSize: 52, bold: true, typeface: FONT, color: C.ink, lineSpacing: 0.95,
    });
    addText(slide, "深圳大学粤海校区周边场景", 88, 456, 520, 44, {
      fontSize: 27, color: C.blueDeep,
    });
    addText(slide, "八方向风场 · 节点重判 · 20% 换电", 88, 516, 560, 36, {
      fontSize: 21, color: C.muted,
    });
    addText(slide, "项目汇报", 88, 734, 140, 34, { fontSize: 20, bold: true, color: C.ink });
    addText(slide, "2026.11", 88, 780, 150, 30, { fontSize: 18, color: C.muted });
  }

  // 2. Problem and scale
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.pale2;
    addHeader(slide, 2, "问题与仿真场景", "研究问题");
    addText(slide, "卡车沿有向路网行驶，无人机承担部分取件。\n天气变化后，如何保证无人机安全返回卡车？", 82, 168, 580, 112, {
      fontSize: 26, bold: true, color: C.ink, lineSpacing: 1.15,
    });
    addBullet(slide, "每个节点重新观测天气", "风从八个方向进入，按 0–8 m/s、8–14 m/s 和 14 m/s 阈值重判模式。", 84, 310, 560);
    addBullet(slide, "20% 阈值换电", "电量降到 151.2 Wh 时，在当前节点更换为 756 Wh 满电电池。", 84, 430, 560, C.orange);
    await addImage(slide, ASSETS.web3d, 714, 158, 814, 448, {
      alt: "HTML 三维车机协同仿真界面", geometry: "roundRect", radius: "rounded-xl",
    });
    addRect(slide, 1272, 452, 256, 154, "#081A24");
    addText(slide, "新版电池参数", 1290, 470, 220, 24, { fontSize: 15, bold: true, color: C.blue });
    addText(slide, "756 Wh", 1290, 508, 104, 34, { fontSize: 24, bold: true, color: C.white });
    addText(slide, "151.2 Wh", 1404, 508, 106, 34, { fontSize: 22, bold: true, color: C.white, align: "right" });
    addText(slide, "额定容量", 1290, 548, 104, 22, { fontSize: 13, color: C.muted });
    addText(slide, "20% 阈值", 1404, 548, 106, 22, { fontSize: 13, color: C.muted, align: "right" });
    addText(slide, "HTML 三维仿真界面，支持四种调度场景切换和轨迹回放", 724, 616, 790, 28, { fontSize: 16, color: C.muted });
    addMetricCard(slide, "4.12 × 3.99 km", "覆盖范围", 84, 682, 330);
    addMetricCard(slide, "2,106", "建筑轮廓", 438, 682, 260);
    addMetricCard(slide, "2,031", "道路折线", 722, 682, 260);
    addMetricCard(slide, "55", "取件订单", 1006, 682, 260);
    addMetricCard(slide, "4 组", "对比场景", 1290, 682, 238, C.blueDeep);
    addFooter(slide, 2, "场景数据：项目 map.json、orders.json");
  }

  // 3. Scene data
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.white;
    addHeader(slide, 3, "三维场景与数据来源", "OSM 冻结数据");
    addRect(slide, 72, 158, 930, 624, C.pale2, { radius: "rounded-xl" });
    await addImage(slide, ASSETS.overview, 86, 172, 902, 596, {
      alt: "粤海校区周边三维场景总览", fit: "contain", geometry: "roundRect", radius: "rounded-xl",
    });
    addText(slide, "建筑高度处理", 1050, 176, 420, 42, { fontSize: 30, bold: true, color: C.ink });
    const rows = [
      ["209", "地图高度标签", C.blueDeep],
      ["857", "层数换算，按 3.2 m/层", C.blue],
      ["1,040", "按建筑类型估高", C.gray],
    ];
    rows.forEach(([v, label, color], i) => {
      const yy = 252 + i * 130;
      addRect(slide, 1050, yy, 420, 102, C.pale2, { radius: "rounded-xl" });
      addRect(slide, 1050, yy, 12, 102, color);
      addText(slide, v, 1086, yy + 18, 126, 48, { fontSize: 34, bold: true, color: C.ink });
      addText(slide, label, 1210, yy + 28, 234, 42, { fontSize: 19, color: C.muted, valign: "middle" });
    });
    addText(slide, "建模范围", 1050, 650, 180, 30, { fontSize: 22, bold: true, color: C.ink });
    addText(slide, "LoD1 建筑体块，地面按平面处理；飞行航段检查建筑净空。", 1050, 694, 420, 74, {
      fontSize: 20, color: C.muted, lineSpacing: 1.14,
    });
    addFooter(slide, 3, "道路与建筑轮廓来自 OpenStreetMap；高度缺失时按项目规则补全");
  }

  // 4. Environment configuration
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.white;
    addHeader(slide, 4, "环境配置", "复现实验");
    addText(slide, "工程分为数值仿真、三维建模和浏览器回放三部分，使用同一份 config.json 与结果 JSON。", 82, 158, 1390, 42, {
      fontSize: 25, bold: true, color: C.ink,
    });
    const columns = [
      {
        n: "01", title: "基础运行环境", x: 82,
        lines: ["Windows 11 x64", "Conda 环境：szu_yuehai_sim", "Python 3.11.15"],
      },
      {
        n: "02", title: "计算与优化", x: 562,
        lines: ["NumPy 2.4.6", "SciPy 1.17.1", "GDAL 3.13.3", "SciPy MILP，底层求解器 HiGHS"],
      },
      {
        n: "03", title: "建模与回放", x: 1042,
        lines: ["Blender 4.3.2", "HTML5 Canvas 与 WebGL", "Pillow 与 FFmpeg 用于视频输出"],
      },
    ];
    columns.forEach((col, i) => {
      if (i > 0) addLine(slide, col.x - 42, 238, 0, 390, C.line, 2);
      addText(slide, col.n, col.x, 238, 72, 48, { fontSize: 32, bold: true, color: i === 1 ? C.orange : C.blueDeep });
      addText(slide, col.title, col.x, 302, 390, 42, { fontSize: 27, bold: true, color: C.ink });
      col.lines.forEach((line, j) => {
        addRect(slide, col.x, 374 + j * 72, 10, 10, j === col.lines.length - 1 && i === 1 ? C.orange : C.blue, { geometry: "ellipse" });
        addText(slide, line, col.x + 28, 364 + j * 72, 390, 42, { fontSize: 21, color: C.ink, valign: "middle" });
      });
    });
    addRect(slide, 82, 674, 1436, 120, C.blueDeep, { radius: "rounded-xl" });
    addText(slide, "运行顺序", 116, 700, 150, 30, { fontSize: 21, bold: true, color: C.white });
    addText(slide, "python simulate.py    python verify.py    Blender 生成场景    浏览器打开 HTML 回放", 284, 696, 1188, 42, {
      fontSize: 23, bold: true, color: C.white, align: "center", valign: "middle",
    });
    addFooter(slide, 4, "版本信息来自当前 szu_yuehai_sim 环境；网页端不依赖后端服务");
  }

  // 5. Simulation design
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.pale2;
    addHeader(slide, 5, "仿真设计", "系统结构");
    addRect(slide, 72, 158, 560, 646, C.white, { radius: "rounded-xl", line: { style: "solid", fill: C.line, width: 1 } });
    addText(slide, "状态驱动的离散事件仿真", 110, 190, 470, 38, { fontSize: 27, bold: true, color: C.ink });
    const stages = [
      ["输入", "map.json、55 个订单、车辆与风场参数"],
      ["状态", "卡车节点、当前时间、无人机电量和已完成订单"],
      ["事件", "到达、观测、起飞、取件、回收和换电"],
      ["输出", "轨迹、逐单决策、天气记录与电量记录"],
    ];
    stages.forEach(([label, body], i) => {
      const y = 260 + i * 124;
      addText(slide, String(i + 1).padStart(2, "0"), 110, y, 58, 34, { fontSize: 20, bold: true, color: i === 2 ? C.orange : C.blueDeep });
      addText(slide, label, 184, y, 100, 34, { fontSize: 23, bold: true, color: C.ink });
      addText(slide, body, 184, y + 42, 380, 58, { fontSize: 18, color: C.muted, lineSpacing: 1.16 });
      if (i < stages.length - 1) addLine(slide, 110, y + 106, 446, 0, C.line, 1);
    });

    addText(slide, "四组对照场景", 690, 190, 320, 38, { fontSize: 27, bold: true, color: C.ink });
    const values = [
      ["场景", "天气", "调度方法", "对照作用"],
      ["纯卡车", "不派无人机", "道路最短路", "基准组"],
      ["常规风况", "0–8 m/s", "逐站分配", "天气基准"],
      ["突发强风", "0–14 m/s", "逐站分配", "风况扰动"],
      ["强风滚动规划", "0–14 m/s", "滚动 MILP", "策略对照"],
    ];
    const table = slide.tables.add({
      rows: 5, columns: 4, left: 690 * S, top: 252 * S, width: 838 * S, height: 430 * S,
      columnWidths: [224, 178, 224, 212].map((v) => v * S), values,
    });
    table.borders.assign({ style: "solid", fill: C.line, width: 1 });
    for (let r = 0; r < 5; r++) {
      for (let c = 0; c < 4; c++) {
        const cell = table.getCell(r, c);
        cell.fill = r === 0 ? C.blueDeep : (r === 4 ? C.pale : (r % 2 === 0 ? C.pale2 : C.white));
        cell.text.style = {
          typeface: FONT, fontSize: (r === 0 ? 20 : 19) * S, bold: r === 0 || r === 4,
          color: r === 0 ? C.white : C.ink, alignment: c === 0 ? "left" : "center", verticalAlignment: "middle",
          autoFit: "shrinkText", insets: { left: 10 * S, right: 8 * S, top: 6 * S, bottom: 6 * S },
        };
      }
    }
    addText(slide, "所有场景使用同一批订单和同一张路网，保证对比口径一致。", 690, 714, 838, 44, {
      fontSize: 21, bold: true, color: C.blueDeep, align: "center",
    });
    addFooter(slide, 5, "验证项：订单唯一服务、载重、时间单调、电量守恒、换电记录和最终回仓");
  }

  // 6. Solution method
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.white;
    addHeader(slide, 6, "解决方法", "滚动决策");
    const steps = [
      ["01", "路网与订单", "构造有向道路图，计算卡车最短时间路径。"],
      ["02", "节点观测", "卡车到达节点后重新读取风速、风向和电量。"],
      ["03", "可行性筛选", "检查载重、建筑净空、能耗、风速和安全距离。"],
      ["04", "滚动优化", "在后续 14 个节点内求解 MILP，只执行当前决策。"],
      ["05", "事件执行", "更新轨迹与电量，必要时换电或转为纯卡车。"],
    ];
    steps.forEach(([n, title, body], i) => {
      const x = 72 + i * 302;
      if (i < 4) addLine(slide, x + 258, 290, 42, 0, C.line, 5);
      addText(slide, n, x, 202, 68, 42, { fontSize: 28, bold: true, color: i === 3 ? C.orange : C.blueDeep });
      addText(slide, title, x, 258, 250, 38, { fontSize: 24, bold: true, color: C.ink });
      addText(slide, body, x, 316, 250, 102, { fontSize: 18, color: C.muted, lineSpacing: 1.18 });
    });
    addLine(slide, 72, 466, 1456, 0, C.line, 2);
    addText(slide, "核心可行性判定", 72, 500, 300, 36, { fontSize: 27, bold: true, color: C.ink });
    const rules = [
      ["载重", "qⱼ ≤ 2 kg"],
      ["航段风速", "0 ≤ ‖w‖ ≤ 14 m/s"],
      ["电量", "Bᵢ⁺ ≥ Ēᵢⱼₖ + 151.2 Wh"],
      ["安全距离", "dᵢⱼ+dⱼₖ ≤ (16−14)tᵤₛₑ"],
    ];
    rules.forEach(([label, formula], i) => {
      const x = 72 + i * 366;
      addText(slide, label, x, 574, 320, 30, { fontSize: 19, bold: true, color: i === 3 ? C.orange : C.blueDeep });
      addText(slide, formula, x, 622, 326, 50, { fontSize: 23, bold: true, color: C.ink, typeface: FONT_LIGHT });
    });
    addRect(slide, 72, 714, 1456, 82, C.pale2, { radius: "rounded-xl" });
    addText(slide, "调度器每到一个节点重新计算，不沿用上一节点的天气判断。", 104, 736, 1392, 36, {
      fontSize: 23, bold: true, color: C.blueDeep, align: "center",
    });
    slide.speakerNotes.text = [
      "模型基础参考 Murray and Chu (2015), DOI: 10.1016/j.trc.2015.03.005。",
      "滚动优化与 TSP-D 方法参考 Agatz, Bouman and Schmidt (2018), DOI: 10.1287/trsc.2017.0791。",
    ];
    addFooter(slide, 6, "最坏地速为 2 m/s；HiGHS 单次求解时限 1.5 s，允许间隙 3%");
  }

  // 7. Revised simulation parameters
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.white;
    addHeader(slide, 7, "修订后的仿真参数", "参数设置");
    const values = [
      ["参数", "仿真值", "参数", "仿真值"],
      ["最大快递载重 Qmax", "2 kg", "电池额定容量 Emax", "756 Wh"],
      ["安全剩余电量比例", "20%", "可规划使用电量", "604.8 Wh"],
      ["空载每公里耗电", "25 Wh/km", "满载每公里耗电", "50 Wh/km"],
      ["巡航空速", "16 m/s", "环境风速范围", "0–14 m/s"],
      ["常规风况范围", "0–8 m/s", "取件服务时间", "60 s"],
    ];
    const table = slide.tables.add({
      rows: 6, columns: 4, left: 72 * S, top: 188 * S, width: 1456 * S, height: 480 * S,
      columnWidths: [420, 250, 420, 366].map((v) => v * S), values,
    });
    table.borders.assign({ style: "solid", fill: C.line, width: 1 });
    for (let r = 0; r < 6; r++) {
      for (let c = 0; c < 4; c++) {
        const cell = table.getCell(r, c);
        cell.fill = r === 0 ? C.blueDeep : (r % 2 === 0 ? C.pale2 : C.white);
        cell.text.style = {
          typeface: FONT, fontSize: (r === 0 ? 22 : 21) * S, bold: r === 0 || c === 1 || c === 3,
          color: r === 0 ? C.white : (c === 1 || c === 3 ? C.blueDeep : C.ink),
          alignment: c === 1 || c === 3 ? "center" : "left", verticalAlignment: "middle",
          autoFit: "shrinkText", insets: { left: 14 * S, right: 10 * S, top: 6 * S, bottom: 6 * S },
        };
      }
    }
    addRect(slide, 72, 710, 1456, 86, C.pale2, { radius: "rounded-xl" });
    addText(slide, "完整环境覆盖八个来风方向和 0–14 m/s。换电操作时间暂取 120 s，作为仿真假设。", 106, 730, 1388, 46, {
      fontSize: 21, color: C.ink, align: "center", valign: "middle",
    });
    addFooter(slide, 7, "20% 安全阈值 = 151.2 Wh；可规划电量 = 756 − 151.2 = 604.8 Wh");
  }

  // 8. Cooperative task structure
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.pale2;
    addHeader(slide, 8, "车机协同任务结构", "模型结构");
    addRect(slide, 72, 164, 868, 612, C.white, { radius: "rounded-xl", line: { style: "solid", fill: C.line, width: 1 } });
    addText(slide, "一次无人机任务由发射点、客户点和会合点组成", 112, 198, 760, 40, { fontSize: 25, bold: true });
    addText(slide, "卡车路线", 112, 284, 120, 28, { fontSize: 18, bold: true, color: C.blueDeep });
    addLine(slide, 190, 420, 580, 0, C.blueDeep, 7);
    addNode(slide, "发射点 i", 150, 390, C.blueDeep, 150);
    addNode(slide, "会合点 k", 670, 390, C.blueDeep, 150);
    addRect(slide, 410, 382, 82, 78, C.pale, { radius: "rounded-xl", line: { style: "solid", fill: C.blue, width: 2 } });
    addText(slide, "卡车", 410, 382, 82, 78, { fontSize: 22, bold: true, color: C.blueDeep, align: "center", valign: "middle" });
    addLine(slide, 270, 388, 215, -128, C.orange, 4);
    addLine(slide, 485, 260, 250, 128, C.orange, 4);
    addNode(slide, "客户点 j", 420, 220, C.orange, 142);
    addText(slide, "空载去程", 280, 286, 120, 26, { fontSize: 18, color: C.orange, align: "center" });
    addText(slide, "载货返程", 602, 286, 120, 26, { fontSize: 18, color: C.orange, align: "center" });
    addRect(slide, 118, 550, 756, 154, C.pale2, { radius: "rounded-xl" });
    addText(slide, "任务结束后，无人机回到卡车并继续使用当前剩余电量。\n若返程风况超限，则在客户点落地等待卡车接回。", 148, 582, 690, 88, {
      fontSize: 22, color: C.ink, lineSpacing: 1.2,
    });
    addText(slide, "基本约束", 1000, 180, 420, 42, { fontSize: 30, bold: true });
    addBullet(slide, "唯一服务", "每个订单只能由卡车或无人机完成一次。", 1000, 254, 470);
    addBullet(slide, "同步会合", "无人机返程后必须与卡车在选定节点会合。", 1000, 372, 470);
    addBullet(slide, "载荷与天气", "载荷不超 2 kg，航段风速不超 14 m/s。", 1000, 490, 470, C.orange);
    addBullet(slide, "连续电量与换电", "电量降到 20% 阈值后，卡车在节点更换电池。", 1000, 608, 470, C.blueDeep);
    addFooter(slide, 8, "模型参数：config.json");
  }

  // 9. Decision variables and objective
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.white;
    addHeader(slide, 9, "决策变量与目标函数", "优化模型");
    addRect(slide, 72, 160, 704, 630, C.pale2, { radius: "rounded-xl" });
    addText(slide, "决策变量", 112, 194, 260, 38, { fontSize: 29, bold: true, color: C.ink });
    addText(slide, "路径与任务分配", 112, 254, 280, 32, { fontSize: 22, bold: true, color: C.blueDeep });
    const routeVars = [
      ["xᵢₖ ∈ {0,1}", "卡车是否行驶道路边 (i,k)"],
      ["yᵢⱼₖ ∈ {0,1}", "无人机是否执行 i 到 j 到 k 的任务"],
      ["uⱼ , vᵢ , rᵢ ∈ {0,1}", "客户服务、节点访问与节点换电决策"],
    ];
    routeVars.forEach(([symbol, meaning], i) => {
      const yy = 306 + i * 76;
      addText(slide, symbol, 112, yy, 238, 34, { fontSize: 23, bold: true, color: C.blueDeep });
      addText(slide, meaning, 362, yy + 2, 362, 42, { fontSize: 18, color: C.muted, valign: "middle" });
      if (i < 2) addLine(slide, 112, yy + 56, 612, 0, C.line, 1);
    });
    addText(slide, "状态与时间", 112, 548, 280, 32, { fontSize: 22, bold: true, color: C.orange });
    const stateVars = [
      ["Aᵢ , Dᵢ", "卡车到达和离开节点的计划时间"],
      ["Lᵢ , Bᵢ⁻ / Bᵢ⁺", "卡车载荷，以及换电前后的剩余电量"],
      ["hⱼ", "客户计划延误时间"],
    ];
    stateVars.forEach(([symbol, meaning], i) => {
      const yy = 600 + i * 62;
      addText(slide, symbol, 112, yy, 190, 32, { fontSize: 22, bold: true, color: C.orange });
      addText(slide, meaning, 304, yy + 1, 420, 36, { fontSize: 18, color: C.muted, valign: "middle" });
    });

    addText(slide, "目标函数", 840, 194, 280, 38, { fontSize: 29, bold: true, color: C.ink });
    addText(slide, "min Z = cₜ Σ dᵀᵢₖxᵢₖ + cₑ Σ Ēᵢⱼₖyᵢⱼₖ", 840, 266, 650, 56, {
      fontSize: 31, bold: true, color: C.blueDeep, typeface: FONT_LIGHT,
    });
    addText(slide, "+ cₜᵢₘₑ D_d + cₗ Σ hⱼ + c_B Σ rᵢ", 840, 330, 620, 52, {
      fontSize: 31, bold: true, color: C.blueDeep, typeface: FONT_LIGHT,
    });
    addText(slide, "Ēᵢⱼₖ = Σω pω Eᵢⱼₖ(ω)", 840, 410, 520, 40, { fontSize: 23, color: C.muted });
    addLine(slide, 840, 474, 640, 0, C.line, 2);
    const terms = [
      ["卡车里程成本", "减少道路运输里程"],
      ["无人机期望能耗", "控制多次飞行耗电"],
      ["总作业时间", "计入行驶、等待和操作时间"],
      ["客户延误", "约束服务时效"],
    ];
    terms.forEach(([name, desc], i) => {
      const yy = 512 + i * 60;
      addRect(slide, 840, yy + 7, 10, 10, i === 1 ? C.orange : C.blue, { geometry: "ellipse" });
      addText(slide, name, 866, yy, 220, 30, { fontSize: 20, bold: true });
      addText(slide, desc, 1094, yy + 1, 380, 30, { fontSize: 18, color: C.muted });
    });
    addRect(slide, 840, 756, 640, 62, C.blueDeep, { radius: "rounded-xl" });
    addText(slide, "安全回收写入硬约束，不用成本项抵消风险。", 866, 771, 588, 34, {
      fontSize: 20, bold: true, color: C.white, align: "center", valign: "middle",
    });
    addFooter(slide, 9, "Bᵢ⁻/Bᵢ⁺ 记录换电前后电量；rᵢ=1 表示在节点 i 更换电池");
  }

  // 10. Constraints
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.pale2;
    addHeader(slide, 10, "约束条件", "MILP 模型");
    addRect(slide, 72, 158, 704, 646, C.white, { radius: "rounded-xl", line: { style: "solid", fill: C.line, width: 1 } });
    addRect(slide, 824, 158, 704, 646, C.white, { radius: "rounded-xl", line: { style: "solid", fill: C.line, width: 1 } });

    addText(slide, "服务与路径", 110, 188, 260, 34, { fontSize: 25, bold: true, color: C.blueDeep });
    addText(slide, "uⱼ + Σᵢ,ₖ yᵢⱼₖ = 1", 110, 236, 570, 34, { fontSize: 24, bold: true, color: C.ink });
    addText(slide, "每个客户只由卡车或无人机服务一次。", 110, 276, 610, 30, { fontSize: 17, color: C.muted });
    addLine(slide, 110, 322, 628, 0, C.line, 1);

    addText(slide, "卡车路径连续", 110, 342, 260, 32, { fontSize: 23, bold: true, color: C.blueDeep });
    addText(slide, "Σₕ xₕᵢ = Σₖ xᵢₖ = vᵢ ,   vⱼ = uⱼ", 110, 386, 610, 34, { fontSize: 22, bold: true });
    addText(slide, "起点只离开一次，终点只进入一次。", 110, 426, 610, 28, { fontSize: 17, color: C.muted });
    addLine(slide, 110, 470, 628, 0, C.line, 1);

    addText(slide, "车机路径耦合", 110, 490, 260, 32, { fontSize: 23, bold: true, color: C.blueDeep });
    addText(slide, "Σⱼ yᵢⱼₖ ≤ xᵢₖ", 110, 534, 610, 34, { fontSize: 23, bold: true });
    addText(slide, "无人机在 i 起飞并在 k 回收时，卡车必须选择对应道路边。", 110, 574, 610, 48, { fontSize: 17, color: C.muted });
    addLine(slide, 110, 636, 628, 0, C.line, 1);

    addText(slide, "载荷与天气可行性", 110, 656, 300, 32, { fontSize: 23, bold: true, color: C.orange });
    addText(slide, "qⱼ yᵢⱼₖ ≤ Q_D ,   yᵢⱼₖ ≤ γᵢⱼₖ", 110, 700, 610, 34, { fontSize: 22, bold: true });
    addText(slide, "超载或天气风险超限的任务不能起飞。", 110, 740, 610, 30, { fontSize: 17, color: C.muted });

    addText(slide, "电量、安全距离与换电", 862, 188, 360, 34, { fontSize: 25, bold: true, color: C.orange });
    addText(slide, "Bᵢ⁺ ≥ Ēᵢⱼₖ + 151.2 − M_B(1−yᵢⱼₖ)", 862, 230, 610, 32, { fontSize: 19, bold: true, color: C.ink });
    addText(slide, "dᵢⱼ+dⱼₖ ≤ (16−14)tᵤₛₑ + M_D(1−yᵢⱼₖ)", 862, 268, 610, 32, { fontSize: 18, bold: true });
    addText(slide, "Bᵢ⁻ ≤ 151.2 ⇒ rᵢ=1，Bᵢ⁺=756 Wh", 862, 306, 610, 30, { fontSize: 19, bold: true });
    addText(slide, "完整任务保留 20% 电量；到阈值先换电再重判天气。", 862, 342, 610, 26, { fontSize: 16, color: C.muted });
    addLine(slide, 862, 382, 628, 0, C.line, 1);

    addText(slide, "时间递推与同步", 862, 398, 300, 32, { fontSize: 23, bold: true, color: C.blueDeep });
    addText(slide, "Aₖ ≥ Dᵢ + τᵀᵢₖ + 120rᵢ − M_T(1−xᵢₖ)", 862, 440, 610, 32, { fontSize: 19, bold: true });
    addText(slide, "Dₖ ≥ Dᵢ + τ̄ᵢⱼₖ + 60 + 120rᵢ − M_T(1−yᵢⱼₖ)", 862, 478, 610, 34, { fontSize: 18, bold: true });
    addText(slide, "卡车在无人机返回前不能离开；换电暂计 120 s。", 862, 518, 610, 26, { fontSize: 16, color: C.muted });
    addLine(slide, 862, 558, 628, 0, C.line, 1);

    addText(slide, "天气分级与客户延误", 862, 574, 330, 32, { fontSize: 23, bold: true, color: C.blueDeep });
    addText(slide, "0–8 m/s：常规；8–14 m/s：强风；>14 m/s：纯卡车", 862, 616, 610, 32, { fontSize: 18, bold: true });
    addText(slide, "hⱼ ≥ 服务完成时间 − bⱼ ,   hⱼ ≥ 0", 862, 656, 610, 32, { fontSize: 20, bold: true });
    addLine(slide, 862, 704, 628, 0, C.line, 1);

    addText(slide, "变量范围与运营时长", 862, 724, 330, 30, { fontSize: 21, bold: true, color: C.blueDeep });
    addText(slide, "A₀ = 0，D_d ≤ T_max；x、y、u、v、r 为 0–1 变量", 862, 758, 610, 28, { fontSize: 17, color: C.muted });
    addFooter(slide, 10, "安全距离使用最不利地速 16−14=2 m/s；条件式采用 Big-M 线性化");
  }

  // 11. Energy constraints
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.white;
    addHeader(slide, 11, "20% 安全阈值与换电", "核心约束");
    addRect(slide, 72, 166, 760, 592, C.pale2, { radius: "rounded-xl" });
    addText(slide, "安全距离", 118, 204, 260, 38, { fontSize: 28, bold: true });
    addText(slide, "dᵢⱼ+dⱼₖ ≤ (16−14)tᵤₛₑ", 118, 264, 650, 68, { fontSize: 38, bold: true, color: C.blueDeep, typeface: FONT_LIGHT });
    addText(slide, "tᵤₛₑ = (Bᵢ−151.2) / 2880 × 3600", 118, 350, 650, 48, { fontSize: 25, bold: true, color: C.ink });
    addText(slide, "换电条件", 118, 432, 260, 38, { fontSize: 28, bold: true });
    addText(slide, "Bᵢ ≤ 151.2 Wh  ⇒  Bᵢ⁺=756 Wh", 118, 494, 650, 66, { fontSize: 34, bold: true, color: C.orange, typeface: FONT_LIGHT });
    addText(slide, "安全距离用 20% 储备对应的可用飞行时间换算，\n避免把速度与电量直接相乘造成量纲错误。", 118, 602, 630, 70, { fontSize: 21, color: C.muted, lineSpacing: 1.18 });
    addText(slide, "电池容量分配", 898, 204, 420, 38, { fontSize: 28, bold: true });
    addText(slide, "756 Wh", 898, 274, 540, 54, { fontSize: 42, bold: true, color: C.ink });
    addRect(slide, 898, 350, 540, 76, C.pale, { radius: "rounded-full" });
    addRect(slide, 898, 350, 432, 76, C.blue, { radius: "rounded-full" });
    addRect(slide, 1330, 350, 108, 76, C.orange, { radius: "rounded-full" });
    addText(slide, "可规划电量 604.8 Wh", 908, 370, 412, 30, { fontSize: 20, bold: true, color: C.white, align: "center" });
    addText(slide, "151.2", 1332, 370, 104, 30, { fontSize: 18, bold: true, color: C.white, align: "center" });
    addRect(slide, 898, 482, 540, 196, C.pale2, { radius: "rounded-xl", line: { style: "solid", fill: C.line, width: 1 } });
    addText(slide, "节点换电规则", 930, 514, 300, 34, { fontSize: 24, bold: true });
    addText(slide, "每到一个卡车节点先检查电量。低于或等于 20% 时，更换满电电池并增加 120 s 操作时间。", 930, 572, 474, 76, { fontSize: 20, color: C.muted, lineSpacing: 1.16 });
    slide.speakerNotes.text = [
      "无人机能耗建模参考 Stolaroff et al. (2018), DOI: 10.1038/s41467-017-02411-5。",
      "飞行位置、风速和功率数据参考 Rodrigues et al. (2021), DOI: 10.1038/s41597-021-00930-x。",
    ];
    addFooter(slide, 11, "额定容量 756 Wh；20% 阈值 151.2 Wh；可规划使用 604.8 Wh");
  }

  // 12. Rolling solution
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.pale2;
    addHeader(slide, 12, "滚动规划与事件驱动执行", "求解方法");
    const steps = [
      ["01", "读取节点位置与电量"],
      ["02", "观测八方向风况"],
      ["03", "计算能耗与安全距离"],
      ["04", "滚动整数规划选任务"],
      ["05", "执行并检查换电"],
    ];
    steps.forEach(([n, t], i) => {
      const x = 74 + i * 302;
      if (i < 4) addRect(slide, x + 244, 286, 52, 10, C.line);
      addRect(slide, x, 222, 244, 146, i === 3 ? C.blueDeep : C.white, {
        radius: "rounded-xl", line: { style: "solid", fill: i === 3 ? C.blueDeep : C.line, width: 1 },
      });
      addText(slide, n, x + 18, 242, 48, 26, { fontSize: 18, bold: true, color: i === 3 ? C.white : C.blueDeep });
      addText(slide, t, x + 18, 282, 208, 62, { fontSize: 22, bold: true, color: i === 3 ? C.white : C.ink, lineSpacing: 1.12 });
    });
    addRect(slide, 74, 430, 704, 310, C.white, { radius: "rounded-xl", line: { style: "solid", fill: C.line, width: 1 } });
    addText(slide, "调度层", 112, 468, 180, 38, { fontSize: 28, bold: true, color: C.blueDeep });
    addBullet(slide, "目标", "兼顾总作业时间、卡车里程和任务迟到。", 112, 530, 610);
    addBullet(slide, "滚动窗口", "最多查看后续 14 个节点，每到节点重新分类天气。", 112, 630, 610);
    addRect(slide, 822, 430, 704, 310, C.white, { radius: "rounded-xl", line: { style: "solid", fill: C.line, width: 1 } });
    addText(slide, "执行层", 860, 468, 180, 38, { fontSize: 28, bold: true, color: C.orange });
    addBullet(slide, "事件更新", "到达、观测、起飞、取件、返航与换电均更新状态。", 860, 530, 610, C.orange);
    addBullet(slide, "模式切换", "0–8 m/s 常规，8–14 m/s 强风，超 14 m/s 纯卡车。", 860, 630, 610, C.orange);
    addFooter(slide, 12, "求解器：HiGHS；单次时限 1.5 s；允许间隙 3%");
  }

  // 13. Node-level weather observation
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.white;
    addHeader(slide, 13, "逐节点天气重判：节点 8", "执行事件");
    await addImage(slide, ASSETS.overview, 72, 164, 858, 594, { alt: "深圳大学粤海校区三维场景与道路模型", fit: "contain", geometry: "roundRect", radius: "rounded-xl" });
    addRect(slide, 976, 164, 552, 594, C.pale2, { radius: "rounded-xl" });
    addText(slide, "节点观测", 1014, 200, 160, 32, { fontSize: 23, bold: true, color: C.blueDeep });
    addText(slide, "t = 844.2 s", 1190, 202, 266, 30, { fontSize: 18, color: C.muted, align: "right" });
    addText(slide, "东北风 10.74 m/s", 1014, 250, 474, 42, { fontSize: 28, bold: true, color: C.orange });
    addText(slide, "阈值判定：8–14 m/s，进入突发强风模式。", 1014, 304, 474, 54, { fontSize: 20, color: C.ink, lineSpacing: 1.15 });
    addLine(slide, 1014, 380, 474, 0, C.line, 2);
    addText(slide, "订单 49 候选任务", 1014, 410, 300, 32, { fontSize: 23, bold: true, color: C.blueDeep });
    addText(slide, "安全距离上限   1298.1 m\n任务总航程         829.1 m\n最大预测耗电       24.41 Wh", 1014, 458, 474, 112, { fontSize: 21, color: C.ink, lineSpacing: 1.35 });
    addRect(slide, 1014, 602, 474, 102, C.white, { radius: "rounded-xl", line: { style: "solid", fill: C.blue, width: 2 } });
    addText(slide, "结果：满足风速、电量和安全距离约束，允许起飞。", 1044, 626, 414, 54, { fontSize: 21, bold: true, color: C.blueDeep, lineSpacing: 1.15 });
    addFooter(slide, 13, "每到一个卡车节点重新观测，因此运行模式可随路段动态切换");
  }

  // 14. Battery replacement rule
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.pale2;
    addHeader(slide, 14, "20% 阈值换电机制", "电池管理");
    addText(slide, "电量检查发生在卡车节点：先判断是否换电，再观测天气和安排下一任务。", 82, 164, 1380, 44, { fontSize: 27, bold: true });
    const flow = [
      ["①", "节点到达", "读取换电前电量 Bᵢ⁻"],
      ["②", "阈值判断", "Bᵢ⁻ ≤ 151.2 Wh"],
      ["③", "执行换电", "增加 120 s，Bᵢ⁺=756 Wh"],
      ["④", "重新调度", "观测风况并生成候选任务"],
    ];
    flow.forEach(([n, title, body], i) => {
      const x = 82 + i * 366;
      if (i < 3) addRect(slide, x + 314, 360, 46, 8, C.line);
      addRect(slide, x, 258, 320, 222, i === 2 ? C.blueDeep : C.white, { radius: "rounded-xl", line: { style: "solid", fill: i === 2 ? C.blueDeep : C.line, width: 1 } });
      addText(slide, n, x + 24, 282, 42, 34, { fontSize: 25, bold: true, color: i === 2 ? C.white : C.blueDeep });
      addText(slide, title, x + 76, 282, 210, 34, { fontSize: 25, bold: true, color: i === 2 ? C.white : C.ink });
      addText(slide, body, x + 24, 350, 272, 74, { fontSize: 20, color: i === 2 ? C.white : C.muted, align: "center", valign: "middle", lineSpacing: 1.15 });
    });
    addRect(slide, 82, 548, 1436, 154, C.white, { radius: "rounded-xl", line: { style: "solid", fill: C.line, width: 1 } });
    addText(slide, "本次 55 单重跑", 126, 584, 300, 34, { fontSize: 24, bold: true, color: C.blueDeep });
    addText(slide, "滚动规划最低电量 375.28 Wh  >  151.2 Wh", 126, 634, 760, 42, { fontSize: 31, bold: true, color: C.ink });
    addRect(slide, 1040, 586, 400, 76, C.pale, { radius: "rounded-full" });
    addText(slide, "换电 0 次", 1040, 606, 400, 34, { fontSize: 28, bold: true, color: C.blueDeep, align: "center" });
    addText(slide, "规则已启用，但本次运行未达到换电阈值。", 126, 720, 1320, 34, { fontSize: 20, color: C.muted });
    addFooter(slide, 14, "换电时间 120 s 为模型假设，可在 config.json 中调整");
  }

  // 15. Results comparison
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.white;
    addHeader(slide, 15, "四组场景运行结果", "实际重跑结果");
    const values = [
      ["场景与方法", "无人机", "卡车里程", "总时间", "无人机耗电", "接回", "换电"],
      ["纯卡车", "0 单", "53.40 km", "189.43 min", "0 Wh", "0 次", "0 次"],
      ["常规风况，逐站分配", "13 单", "50.42 km", "172.79 min", "375.12 Wh", "0 次", "0 次"],
      ["突发强风，逐站分配", "12 单", "50.75 km", "174.80 min", "379.95 Wh", "0 次", "0 次"],
      ["突发强风，滚动整数规划", "13 单", "49.57 km", "170.21 min", "380.73 Wh", "0 次", "0 次"],
    ];
    const table = slide.tables.add({
      rows: 5, columns: 7, left: 72 * S, top: 176 * S, width: 1456 * S, height: 408 * S,
      columnWidths: [360, 150, 190, 190, 220, 170, 176].map((v) => v * S), values,
    });
    table.borders.assign({ style: "solid", fill: C.line, width: 1 });
    for (let r = 0; r < 5; r++) {
      for (let c = 0; c < 7; c++) {
        const cell = table.getCell(r, c);
        cell.fill = r === 0 ? C.blueDeep : (r === 4 ? C.pale : (r % 2 === 0 ? C.pale2 : C.white));
        cell.text.style = {
          typeface: FONT,
          fontSize: (r === 0 ? 22 : 21) * S,
          bold: r === 0 || r === 4,
          color: r === 0 ? C.white : C.ink,
          alignment: c === 0 ? "left" : "center",
          verticalAlignment: "middle",
          autoFit: "shrinkText",
          insets: { left: (c === 0 ? 16 : 8) * S, right: 8 * S, top: 6 * S, bottom: 6 * S },
        };
      }
    }
    addText(slide, "强风场景内对比", 72, 626, 300, 34, { fontSize: 25, bold: true, color: C.ink });
    const deltas = [
      ["+1 单", "无人机任务"],
      ["−1.18 km", "卡车里程"],
      ["−4.59 min", "总作业时间"],
      ["+0.78 Wh", "无人机耗电"],
    ];
    deltas.forEach(([v, l], i) => {
      const x = 72 + i * 366;
      addRect(slide, x, 680, 340, 116, i === 3 ? "#FFF3EC" : C.pale2, { radius: "rounded-xl", line: { style: "solid", fill: i === 3 ? "#F6C3A8" : C.line, width: 1 } });
      addText(slide, v, x + 22, 700, 296, 42, { fontSize: 31, bold: true, color: i === 3 ? C.orange : C.blueDeep, align: "center" });
      addText(slide, l, x + 22, 754, 296, 24, { fontSize: 17, color: C.muted, align: "center" });
    });
    addFooter(slide, 15, "四组均完成 55 个订单；滚动规划相对强风逐站分配减少 1.18 km 和 4.59 min");
  }

  // 16. References
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.white;
    addHeader(slide, 16, "论文引用", "研究依据");
    addText(slide, "车机协同路径优化", 82, 164, 520, 38, { fontSize: 26, bold: true, color: C.blueDeep });
    const refs = [
      ["[1]", "Murray C C, Chu A G. The flying sidekick traveling salesman problem: Optimization of drone-assisted parcel delivery. Transportation Research Part C, 2015, 54: 86–109.", "DOI: 10.1016/j.trc.2015.03.005"],
      ["[2]", "Agatz N, Bouman P, Schmidt M. Optimization Approaches for the Traveling Salesman Problem with Drone. Transportation Science, 2018, 52(4): 965–981.", "DOI: 10.1287/trsc.2017.0791"],
    ];
    refs.forEach(([n, citation, doi], i) => {
      const y = 224 + i * 174;
      addText(slide, n, 82, y, 72, 34, { fontSize: 23, bold: true, color: C.blueDeep });
      addText(slide, citation, 158, y, 820, 92, { fontSize: 19, color: C.ink, lineSpacing: 1.18 });
      addText(slide, doi, 158, y + 104, 720, 28, { fontSize: 17, color: C.muted });
      if (i === 0) addLine(slide, 158, y + 148, 820, 0, C.line, 1);
    });

    addText(slide, "无人机能耗与飞行数据", 82, 584, 520, 38, { fontSize: 26, bold: true, color: C.orange });
    const energyRefs = [
      ["[3]", "Stolaroff J K, Samaras C, O’Neill E R, et al. Energy use and life cycle greenhouse gas emissions of drones for commercial package delivery. Nature Communications, 2018, 9: 409.", "DOI: 10.1038/s41467-017-02411-5"],
      ["[4]", "Rodrigues T A, Patrikar J, Oliveira N L, et al. In-flight positional and energy use data set of a DJI Matrice 100 quadcopter for small package delivery. Scientific Data, 2021, 8: 155.", "DOI: 10.1038/s41597-021-00930-x"],
    ];
    energyRefs.forEach(([n, citation, doi], i) => {
      const y = 642 + i * 104;
      addText(slide, n, 82, y, 72, 30, { fontSize: 21, bold: true, color: C.orange });
      addText(slide, citation, 158, y, 820, 64, { fontSize: 17, color: C.ink, lineSpacing: 1.12 });
      addText(slide, doi, 158, y + 68, 720, 24, { fontSize: 15, color: C.muted });
    });

    addLine(slide, 1032, 164, 0, 610, C.line, 2);
    addText(slide, "与本研究的对应关系", 1080, 164, 390, 38, { fontSize: 26, bold: true, color: C.ink });
    addBullet(slide, "任务结构", "发射点、客户点和会合点的车机同步关系参考文献 [1]。", 1080, 240, 390);
    addBullet(slide, "优化方法", "整数规划与路线先行思路参考文献 [2]。", 1080, 364, 390);
    addBullet(slide, "能耗参数", "载荷、飞行速度和单位距离耗电设置参考文献 [3]、[4] 的建模思路。", 1080, 488, 390, C.orange);
    addBullet(slide, "本文扩展", "逐节点天气重判、20% 换电和最坏风速安全距离为本项目新增约束。", 1080, 632, 390, C.blueDeep);
    slide.speakerNotes.text = [
      "https://doi.org/10.1016/j.trc.2015.03.005",
      "https://doi.org/10.1287/trsc.2017.0791",
      "https://doi.org/10.1038/s41467-017-02411-5",
      "https://doi.org/10.1038/s41597-021-00930-x",
    ];
    addFooter(slide, 16, "引用格式按作者、题名、期刊、年份、卷期页码和 DOI 排列");
  }

  // 17. Conclusion
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.white;
    addHeader(slide, 17, "结论与仿真边界", "汇报总结");
    addRect(slide, 72, 160, 960, 544, C.pale2, { radius: "rounded-xl" });
    addText(slide, "主要结论", 112, 198, 220, 38, { fontSize: 28, bold: true });
    addBullet(slide, "逐节点观测让模式随天气切换", "卡车到达节点后按 0–8、8–14、超 14 m/s 重新选择运行模式。", 112, 264, 838);
    addBullet(slide, "安全距离约束保持量纲一致", "用 20% 储备对应的可用飞行时间，乘最不利地速 2 m/s。", 112, 382, 838, C.orange);
    addBullet(slide, "换电规则已进入仿真闭环", "低于 151.2 Wh 自动换电；本次最低 375.28 Wh，因此未触发。", 112, 500, 838, C.blueDeep);
    addText(slide, "仿真边界", 1080, 198, 220, 38, { fontSize: 28, bold: true });
    addText(slide, "建筑采用 LoD1 体块\n风向离散为八方向\n风况按航段保持不变\n换电时间 120 s 为假设\n未模拟连续湍流", 1080, 260, 390, 248, { fontSize: 22, color: C.ink, lineSpacing: 1.36 });
    addRect(slide, 1080, 548, 390, 114, C.blueDeep, { radius: "rounded-xl" });
    addText(slide, "下一步：增加订单密度和低初始电量工况，专项验证换电触发。", 1110, 574, 330, 68, { fontSize: 21, bold: true, color: C.white, lineSpacing: 1.15 });
    await addImage(slide, ASSETS.city, 0, 738, 1600, 162, { alt: "深圳大学与深圳城市景观" });
    addRect(slide, 0, 730, 1600, 12, C.blue);
  }

  // Render every slide and a deck montage before finalization.
  for (const [index, slide] of presentation.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    const png = await presentation.export({ slide, format: "png", scale: 1 });
    await writeBlob(path.join(PREVIEW_DIR, `${stem}.png`), png);
  }
  await writeBlob(path.join(PREVIEW_DIR, "deck-montage.webp"), await presentation.export({ format: "webp", montage: true }));

  const { finalizePresentation } = await import(pathToFileURL(path.join(SKILL_DIR, "container_tools", "artifact_tool_utils.mjs")).href);
  const stagingDir = path.join(BUILD_DIR, ".codex-finalizer-v6");
  await fs.mkdir(stagingDir, { recursive: true });
  const candidatePath = path.join(stagingDir, "candidate.pptx");
  await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

  const requirements = {
    explicitTotalSlideCount: 17,
    requiredNativeTableOwnerSlides: [5, 7, 15],
    requiredNativeChartOwnerSlides: [],
  };
  const result = await finalizePresentation({
    ...requirements,
    workspaceDir: WORKSPACE,
    candidatePath,
    finalPath: FINAL_PPTX,
    pythonExecutable: RUNTIME_PYTHON,
    integrityValidatorPath: path.join(SKILL_DIR, "container_tools", "inspect_presentation_package_integrity.py"),
    layoutValidatorPath: path.join(SKILL_DIR, "container_tools", "inspect_presentation_layout_geometry.py"),
    layoutArgs: [
      "--expected-slide-size-emu", "12192000,6858000",
      "--validate-bullet-geometry",
      "--validate-heading-fit",
      "--require-native-table-slide", "5",
      "--require-native-table-slide", "7",
      "--require-native-table-slide", "15",
    ],
    requiredNativeTableOwnerSlides: [5, 7, 15],
    fontPolicy: {
      basis: "design",
      families: [FONT, FONT_LIGHT],
    },
    verifyArtifactToolImport: true,
    receiptPath: path.join(stagingDir, `${path.basename(FINAL_PPTX)}.validation.json`),
  });
  console.log(JSON.stringify({ final: FINAL_PPTX, previews: PREVIEW_DIR, result }, null, 2));
}

build().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
