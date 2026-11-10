import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const source = "C:\\Users\\zh\\Desktop\\建筑PPT模板.pptx";
const outDir = "C:\\Users\\zh\\Desktop\\git\\低空物流系统\\ppt_build_v2\\template_render";

async function saveBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

const deck = await PresentationFile.importPptx(await FileBlob.load(source));
await fs.mkdir(outDir, { recursive: true });
console.log(JSON.stringify({
  slideCount: deck.slides.items.length,
  slideSize: deck.slideSize,
  masters: deck.masters.items.map(m => ({ id: m.id, name: m.name })),
  layouts: deck.layouts.items.map(l => ({ id: l.id, name: l.name, placeholders: l.placeholders.summary() })),
}, null, 2));

const inspection = await deck.inspect({
  select: "$.slides[*]",
  include: ["id", "index", "layout", "title", "elements.id", "elements.kind", "elements.text", "elements.position", "elements.style"],
});
await fs.writeFile(path.join(outDir, "template-inspect.ndjson"), inspection.ndjson, "utf8");

for (let i = 0; i < deck.slides.items.length; i++) {
  const slide = deck.slides.getItemAt(i);
  await saveBlob(path.join(outDir, `slide-${String(i + 1).padStart(2, "0")}.png`), await deck.export({ slide, format: "png", scale: 1 }));
  const layout = await slide.export({ format: "layout", detail: "full" });
  await fs.writeFile(path.join(outDir, `slide-${String(i + 1).padStart(2, "0")}.layout.json`), await layout.text(), "utf8");
}
await saveBlob(path.join(outDir, "template-montage.webp"), await deck.export({ format: "webp", montage: true, scale: .5 }));
