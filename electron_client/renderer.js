const form = document.querySelector("#uploadForm");
const fileInput = document.querySelector("#documentFile");
const chooseFileBtn = document.querySelector("#chooseFileBtn");
const resetBtn = document.querySelector("#resetBtn");
const fileName = document.querySelector("#fileName");
const statusText = document.querySelector("#statusText");
const submitBtn = document.querySelector("#submitBtn");
const contentCard = document.querySelector(".content-card");
const overviewOutput = document.querySelector("#overviewOutput");
const scoringOutput = document.querySelector("#scoringOutput");
const qualificationOutput = document.querySelector("#qualificationOutput");
const priceOutput = document.querySelector("#priceOutput");
const rawOutput = document.querySelector("#rawOutput");
const sectionsTextOutput = document.querySelector("#sectionsTextOutput");
const sectionList = document.querySelector("#sectionList");
const sectionCount = document.querySelector("#sectionCount");
const parseMethod = document.querySelector("#parseMethod");
const enableFormula = document.querySelector("#enableFormula");
const enableTable = document.querySelector("#enableTable");
const viewerModal = document.querySelector("#viewerModal");
const viewerTitle = document.querySelector("#viewerTitle");
const viewerText = document.querySelector("#viewerText");
const viewerCopyBtn = document.querySelector("#viewerCopyBtn");

const PARSE_METHOD_LABELS = {
  mineru_vlm: "MinerU VLM 模型",
  mineru_pipeline: "MinerU Pipeline 模型",
  mineru_html: "MinerU-HTML 模型",
  pdfplumber: "pdfplumber 本地 PDF",
  docx2python: "docx2python 本地 Word"
};

chooseFileBtn.addEventListener("click", () => {
  fileInput.click();
});

parseMethod.addEventListener("change", () => {
  syncMineruOptions();
  refreshSubtitle();
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) {
    fileName.textContent = `已选择：${file.name}`;
    statusText.textContent = "文件已选择，点击下一步开始解析";
    submitBtn.classList.add("ready");
  } else {
    resetView();
  }
});

resetBtn.addEventListener("click", () => {
  form.reset();
  resetView();
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    document
      .querySelectorAll(".tab-panel")
      .forEach((panel) => panel.classList.remove("active"));

    tab.classList.add("active");
    document.querySelector(`#${tab.dataset.tab}`).classList.add("active");
  });
});

document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const target = document.querySelector(`#${button.dataset.copy}`);
    await navigator.clipboard.writeText(getTargetText(target));
    flashButton(button, "已复制");
  });
});

document.querySelectorAll("[data-expand]").forEach((button) => {
  button.addEventListener("click", () => {
    const target = document.querySelector(`#${button.dataset.expand}`);
    openViewer(button.dataset.title || "内容查看", getTargetText(target));
  });
});

document.querySelectorAll("[data-export]").forEach((button) => {
  button.addEventListener("click", () => {
    const target = document.querySelector(`#${button.dataset.export}`);
    exportText(button.dataset.name || "导出内容.txt", getTargetText(target));
  });
});

document.querySelectorAll("[data-close-viewer]").forEach((button) => {
  button.addEventListener("click", closeViewer);
});

viewerCopyBtn.addEventListener("click", async () => {
  await navigator.clipboard.writeText(viewerText.value || "");
  flashButton(viewerCopyBtn, "已复制");
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeViewer();
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = fileInput.files[0];
  if (!file) {
    statusText.textContent = "请先选择一个招标文件";
    return;
  }

  const selectedParseMethod = parseMethod.value;
  const apiBase = document.querySelector("#apiBase").value.trim().replace(/\/$/, "");
  const formData = new FormData();
  formData.append("file", file);
  formData.append("parse_method", selectedParseMethod);
  formData.append("model_version", getMineruModelVersion(selectedParseMethod));
  formData.append("llm_vendor", document.querySelector("#llmVendor").value);
  formData.append("llm_model", document.querySelector("#llmModel").value);
  formData.append("language", document.querySelector("#language").value);
  formData.append("enable_formula", String(enableFormula.checked));
  formData.append("enable_table", String(enableTable.checked));
  formData.append("poll_interval", "5");
  formData.append("timeout", "600");
  formData.append("is_ocr", "false");

  const pageRanges = document.querySelector("#pageRanges").value.trim();
  if (pageRanges) {
    formData.append("page_ranges", pageRanges);
  }

  setLoading(true);
  showResults();
  setOutputs({
    project_overview: `正在使用 ${PARSE_METHOD_LABELS[selectedParseMethod]} 解析文件，并调用所选大模型分析项目概述...`,
    technical_scoring_requirements: "等待 LLM 分析技术评分要求...",
    qualification_compliance_requirements: "等待 LLM 分析资格和符合性审查要求...",
    price_scoring_requirements: "等待 LLM 分析价格评分要求...",
    sections: []
  });

  try {
    if (window.backend?.ensure) {
      statusText.textContent = "正在确认后端服务...";
      await window.backend.ensure(apiBase);
    }

    const response = await fetch(`${apiBase}/bid-documents/upload-analyze`, {
      method: "POST",
      body: formData
    });

    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(text || "后端返回了非 JSON 内容");
    }

    if (!response.ok) {
      throw new Error(data.detail || JSON.stringify(data, null, 2));
    }

    setOutputs(data);
    statusText.textContent = "解析和 LLM 分析完成";
  } catch (error) {
    showResults();
    statusText.textContent = "处理失败";
    overviewOutput.value = error.message || String(error);
    scoringOutput.value = "暂无结果";
    qualificationOutput.value = "暂无结果";
    priceOutput.value = "暂无结果";
    rawOutput.value = error.stack || String(error);
    renderSections([]);
  } finally {
    setLoading(false);
  }
});

function getMineruModelVersion(selectedParseMethod) {
  if (selectedParseMethod === "mineru_pipeline") {
    return "pipeline";
  }
  if (selectedParseMethod === "mineru_html") {
    return "MinerU-HTML";
  }
  return "vlm";
}

function syncMineruOptions() {
  const supportsOptions = parseMethod.value === "mineru_vlm" || parseMethod.value === "mineru_pipeline";
  enableFormula.disabled = !supportsOptions;
  enableTable.disabled = !supportsOptions;
  enableFormula.closest(".check-item").classList.toggle("disabled", !supportsOptions);
  enableTable.closest(".check-item").classList.toggle("disabled", !supportsOptions);
}

function refreshSubtitle() {
  const file = fileInput.files[0];
  if (file) {
    fileName.textContent = `已选择：${file.name}`;
    return;
  }
  fileName.textContent = `当前解析方案：${PARSE_METHOD_LABELS[parseMethod.value]}`;
}

function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  submitBtn.textContent = isLoading ? "处理中..." : "下一步";
  if (isLoading) {
    statusText.textContent = "处理中，文档解析和 LLM 调用可能需要几分钟";
  }
}

function setOutputs(data) {
  overviewOutput.value = data.project_overview || "暂无结果";
  scoringOutput.value = data.technical_scoring_requirements || "暂无结果";
  qualificationOutput.value = data.qualification_compliance_requirements || "暂无结果";
  priceOutput.value = data.price_scoring_requirements || "暂无结果";
  rawOutput.value = JSON.stringify(data, null, 2);
  renderSections(data.sections || []);
}

function renderSections(sections) {
  sectionCount.textContent = `${sections.length} 个章节`;
  sectionList.innerHTML = "";

  if (!sections.length) {
    sectionsTextOutput.value = "";
    const empty = document.createElement("p");
    empty.className = "section-content";
    empty.textContent = "暂无章节";
    sectionList.appendChild(empty);
    return;
  }

  const textParts = [];
  sections.forEach((section) => {
    const titleText = `${section.index}. ${section.title}`;
    const bodyText = section.content || section.markdown || "";
    textParts.push(`${titleText}\n\n${bodyText}`);

    const item = document.createElement("article");
    item.className = "section-item";

    const title = document.createElement("h3");
    title.textContent = titleText;

    const meta = document.createElement("div");
    meta.className = "section-meta";
    meta.textContent = `层级 ${section.level} | ${bodyText.length} 字`;

    const content = document.createElement("pre");
    content.className = "section-content";
    content.textContent = bodyText;

    item.append(title, meta, content);
    sectionList.appendChild(item);
  });
  sectionsTextOutput.value = textParts.join("\n\n------------------------------\n\n");
}

function showResults() {
  contentCard.classList.add("has-result");
}

function resetView() {
  fileName.textContent = `当前解析方案：${PARSE_METHOD_LABELS[parseMethod.value]}`;
  statusText.textContent = "等待上传";
  submitBtn.classList.remove("ready");
  submitBtn.disabled = false;
  submitBtn.textContent = "下一步";
  contentCard.classList.remove("has-result");
  overviewOutput.value = "暂无结果";
  scoringOutput.value = "暂无结果";
  qualificationOutput.value = "暂无结果";
  priceOutput.value = "暂无结果";
  rawOutput.value = "暂无结果";
  sectionsTextOutput.value = "";
  renderSections([]);
  syncMineruOptions();
}

function getTargetText(target) {
  if (!target) {
    return "";
  }
  return "value" in target ? target.value : target.textContent || "";
}

function openViewer(title, text) {
  viewerTitle.textContent = title;
  viewerText.value = text || "暂无内容";
  viewerModal.classList.add("open");
  viewerModal.setAttribute("aria-hidden", "false");
  setTimeout(() => viewerText.focus(), 0);
}

function closeViewer() {
  viewerModal.classList.remove("open");
  viewerModal.setAttribute("aria-hidden", "true");
}

function exportText(fileName, text) {
  const blob = new Blob([text || ""], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function flashButton(button, text) {
  const original = button.textContent;
  button.textContent = text;
  setTimeout(() => {
    button.textContent = original;
  }, 1200);
}

syncMineruOptions();
refreshSubtitle();
