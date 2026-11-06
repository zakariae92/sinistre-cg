// Citation click -> render the PDF page with PDF.js and highlight the clause lines in yellow.
const docs = {};

async function loadDoc(contract) {
  if (!docs[contract]) {
    pdfjsLib.GlobalWorkerOptions.workerSrc =
      "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
    docs[contract] = pdfjsLib.getDocument(`/pdf/${contract}`).promise;
  }
  return docs[contract];
}

async function renderPage(doc, num, boxes, container) {
  const page = await doc.getPage(num);
  const width = container.clientWidth - 16;
  const viewport = page.getViewport({ scale: width / page.getViewport({ scale: 1 }).width });
  const wrap = document.createElement("div");
  wrap.className = "pdf-page";
  wrap.style.width = `${viewport.width}px`;
  wrap.style.height = `${viewport.height}px`;
  const canvas = document.createElement("canvas");
  canvas.width = viewport.width * devicePixelRatio;
  canvas.height = viewport.height * devicePixelRatio;
  canvas.style.width = "100%";
  wrap.appendChild(canvas);
  container.appendChild(wrap);
  const ctx = canvas.getContext("2d");
  ctx.scale(devicePixelRatio, devicePixelRatio);
  await page.render({ canvasContext: ctx, viewport }).promise;
  // PyMuPDF boxes are in PDF points, origin top-left: only a scale is needed.
  for (const [p, x0, y0, x1, y1] of boxes) {
    if (p !== num) continue;
    const hl = document.createElement("div");
    hl.className = "hl";
    Object.assign(hl.style, {
      left: `${x0 * viewport.scale}px`, top: `${y0 * viewport.scale}px`,
      width: `${(x1 - x0) * viewport.scale}px`, height: `${(y1 - y0) * viewport.scale}px`,
    });
    wrap.appendChild(hl);
  }
  return wrap;
}

document.addEventListener("click", async (ev) => {
  const btn = ev.target.closest(".cite");
  if (!btn) return;
  const { contract, page } = btn.dataset;
  const boxes = JSON.parse(btn.dataset.bboxes);
  const pages = document.getElementById("pdf-pages");
  if (!pages) { window.open(`/pdf/${contract}#page=${page}`, "_blank"); return; }
  document.getElementById("pdf-titre").textContent = `${btn.title}`;
  const src = document.getElementById("pdf-source");
  src.href = btn.dataset.source; src.classList.toggle("hidden", !btn.dataset.source);
  pages.innerHTML = '<p class="text-sm text-slate-500 p-4">Chargement du PDF…</p>';
  const doc = await loadDoc(contract);
  const nums = [...new Set(boxes.map((b) => b[0]))].slice(0, 3);
  pages.innerHTML = "";
  let first = null;
  for (const n of nums.length ? nums : [Number(page)]) {
    const el = await renderPage(doc, n, boxes, pages);
    first = first || el;
  }
  const hl = first.querySelector(".hl");
  document.getElementById("pdf-zone").scrollTop = (hl ? hl.offsetTop + first.offsetTop - 80 : 0);
});
