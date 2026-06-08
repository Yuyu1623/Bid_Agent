const form = document.querySelector("#uploadForm");
const fileInput = document.querySelector("#documentFile");
const chooseFileBtn = document.querySelector("#chooseFileBtn");
const resetBtn = document.querySelector("#resetBtn");
const fileName = document.querySelector("#fileName");
const statusText = document.querySelector("#statusText");
const parseDuration = document.querySelector("#parseDuration");
const parseQuality = document.querySelector("#parseQuality");
const submitBtn = document.querySelector("#submitBtn");
const reviewDoneBtn = document.querySelector("#reviewDoneBtn");
const stepKicker = document.querySelector("#stepKicker");
const stepTitle = document.querySelector("#stepTitle");
const contentCard = document.querySelector(".content-card");
const generationTopPanel = document.querySelector("#generationTopPanel");
const noticeFields = document.querySelector("#noticeFields");
const businessOutput = document.querySelector("#businessOutput");
const technicalOutput = document.querySelector("#technicalOutput");
const qualificationTables = document.querySelector("#qualificationTables");
const scoringTables = document.querySelector("#scoringTables");
const parsedMarkdownOutput = document.querySelector("#parsedMarkdownOutput");
const contentReviewOutput = document.querySelector("#contentReviewOutput");
const runContentReviewBtn = document.querySelector("#runContentReviewBtn");
const contentReviewModel = document.querySelector("#contentReviewModel");
const contentReviewDeepThinking = document.querySelector("#contentReviewDeepThinking");
const reanalyzeEditedBtn = document.querySelector("#reanalyzeEditedBtn");
const parseMethod = document.querySelector("#parseMethod");
const enableDeepThinking = document.querySelector("#enableDeepThinking");
const enableFormula = document.querySelector("#enableFormula");
const enableTable = document.querySelector("#enableTable");
const llmModel = document.querySelector("#llmModel");
const viewerModal = document.querySelector("#viewerModal");
const viewerTitle = document.querySelector("#viewerTitle");
const viewerRich = document.querySelector("#viewerRich");
const viewerText = document.querySelector("#viewerText");
const viewerSaveBtn = document.querySelector("#viewerSaveBtn");
const viewerCopyBtn = document.querySelector("#viewerCopyBtn");
let activeViewerTarget = null;
let parseStartTime = 0;
let lastAnalysisResult = {};
let lastParsedSections = [];

const PARSE_METHOD_LABELS = {
  auto: "智能推荐解析",
  mineru_vlm: "MinerU VLM 模型",
  mineru_pipeline: "MinerU Pipeline 模型",
  mineru_html: "MinerU-HTML 模型",
  mineru_parallel_pages: "MinerU 并行页段",
  mineru_local_pipeline: "本地 MinerU Pipeline",
  pymupdf4llm: "PyMuPDF4LLM 快速 PDF",
  docling: "Docling 结构化 PDF",
  pdfplumber: "本地 pdfplumber PDF",
  docx2python: "本地 docx2python Word",
  docx2python_image_ocr: "本地 docx2python + RapidOCR Word"
};

const NOTICE_FIELDS = [
  ["项目名称", "项目名称"],
  ["项目编号", "项目编号"],
  ["项目类别（服务类，货物类，工程类）和服务年限", "项目类别（服务类，货物类，工程类）和服务年限"],
  ["包号", "包号"],
  ["项目规模和预算", "项目规模和预算"],
  ["招标人", "招标人"],
  ["招标代理机构", "招标代理机构"],
  ["项目所属领域", "项目所属领域"],
  ["项目时间安排", "项目时间安排"],
  ["项目要实施的具体内容", "项目要实施的具体内容"],
  ["主要技术特点", "主要技术特点"],
  ["其他关键要求", "其他关键要求"]
];

const NOTICE_BOOLEAN_FIELDS = [
  ["是否专门面向中小微企业采购", "是否专门面向中小微企业采购"],
  ["是否为暗标", "是否为暗标"]
];

const DEEP_THINKING_MODELS = new Set([
  "DeepSeek-R1 (Pro)",
  "Qwen3.6-35B-A3B",
  "Qwen3-8B (轻量)",
  "DeepSeek-R1-Distill-Qwen-7B (轻量)"
]);

chooseFileBtn.addEventListener("click", () => fileInput.click());

parseMethod.addEventListener("change", () => {
  syncMineruOptions();
  refreshSubtitle();
});

llmModel.addEventListener("change", syncDeepThinkingOption);
contentReviewModel?.addEventListener("change", syncContentReviewDeepThinkingOption);

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

reviewDoneBtn.addEventListener("click", () => {
  if (!getTargetText(parsedMarkdownOutput).trim()) {
    statusText.textContent = "请先完成招标文件解析和核对";
    return;
  }
  setWorkflowStep(3);
  activateTab("parsed");
  statusText.textContent = "核对完成，已进入标书生成步骤";
});

reanalyzeEditedBtn?.addEventListener("click", async () => {
  const apiBase = getApiBase();
  const fileContent = getTargetText(parsedMarkdownOutput).trim();
  if (!fileContent) {
    statusText.textContent = "请先在解析原文中保留或填写要分析的内容";
    return;
  }

  setLoading(true);
  showResults();
  clearAnalysisOutputs();
  try {
    await ensureBackendReady(apiBase);

    statusText.textContent = "正在使用修改后的解析内容重新分析...";
    const payload = {
      file_content: fileContent,
      llm_vendor: document.querySelector("#llmVendor").value,
      llm_model: llmModel.value,
      stream_output: document.querySelector("#streamOutput").value === "true",
      enable_deep_thinking: isDeepThinkingEnabled()
    };

    if (payload.stream_output) {
      await runStreamingEditedAnalyze(apiBase, payload);
    } else {
      const response = await fetch(`${apiBase}/bid-documents/analyze-content`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const text = await response.text();
      const data = JSON.parse(text);
      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail || data, null, 2)
        );
      }
      setOutputs(data);
      setParsedSections(data.sections || []);
      setWorkflowStep(2);
      activateTab("parsed");
      statusText.textContent = "修改内容重新分析完成";
    }
  } catch (error) {
    const detail = formatErrorDetail(error, apiBase);
    statusText.textContent = "修改内容分析失败，详情已写入结果区";
    renderBusinessContent(detail);
    renderTechnicalContent(detail);
  } finally {
    setLoading(false);
  }
});

runContentReviewBtn?.addEventListener("click", async () => {
  const apiBase = getApiBase();
  if (!lastParsedSections.length) {
    statusText.textContent = "请先完成文件解析，再执行内容审查";
    renderContentReviewContent("暂无可审查的解析章节。请先上传并解析招标文件。");
    return;
  }

  runContentReviewBtn.disabled = true;
  renderContentReviewContent("正在执行正则内容审查...");
  try {
    await ensureBackendReady(apiBase);
    const response = await fetch(`${apiBase}/bid-documents/content-review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sections: lastParsedSections,
        file_content: sectionsToMarkdown(lastParsedSections),
        extracted: collectExtractedForReview(),
        llm_vendor: document.querySelector("#llmVendor").value,
        llm_model: contentReviewModel?.value || "",
        enable_deep_thinking: isContentReviewDeepThinkingEnabled()
      })
    });
    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(text || "后端返回了非 JSON 内容");
    }
    if (!response.ok) {
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail || data, null, 2)
      );
    }
    renderContentReviewContent(data.content_review_markdown || "内容审查暂无结果");
    lastAnalysisResult = {
      ...lastAnalysisResult,
      content_review_markdown: data.content_review_markdown || "",
      content_review_report: data.content_review_report || {}
    };
    activateTab("contentReview");
    statusText.textContent = "内容审查完成";
  } catch (error) {
    const detail = formatErrorDetail(error, apiBase);
    renderContentReviewContent(detail);
    statusText.textContent = "内容审查失败，详情已写入内容审查区";
  } finally {
    runContentReviewBtn.disabled = false;
  }
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    activateTab(tab.dataset.tab);
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
    openViewer(button.dataset.title || "内容查看", getTargetText(target), target);
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

viewerSaveBtn.addEventListener("click", () => {
  if (!activeViewerTarget || !("value" in activeViewerTarget)) {
    return;
  }
  activeViewerTarget.value = viewerText.value || "";
  flashButton(viewerSaveBtn, "已保存");
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

  const selectedParseMethod = resolveClientParseMethod(file, parseMethod.value);
  const apiBase = getApiBase();
  const formData = new FormData();
  formData.append("file", file);
  formData.append("parse_method", selectedParseMethod);
  formData.append("model_version", getMineruModelVersion(selectedParseMethod));
  formData.append("llm_vendor", document.querySelector("#llmVendor").value);
  formData.append("llm_model", llmModel.value);
  formData.append("stream_output", document.querySelector("#streamOutput").value);
  formData.append("enable_deep_thinking", String(isDeepThinkingEnabled()));
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
  startParseTimer();
  showResults();
  lastAnalysisResult = {};
  lastParsedSections = [];
  setOutputs({
    project_overview: `正在使用 ${PARSE_METHOD_LABELS[selectedParseMethod]} 解析文件，并提取五大模块...`,
    technical_scoring_requirements: "等待 LLM 提取技术要求...",
    business_content: "等待 LLM 提取商务内容...",
    qualification_compliance_requirements: "",
    price_scoring_requirements: "",
    image_analysis_markdown: "图片解析等待中...",
    content_review_markdown: "内容审查尚未执行。五大模块提取完成后，可点击“执行审查”。"
  });
  renderParseQuality(null);

  try {
    await ensureBackendReady(apiBase);

    statusText.textContent = "后端连接正常，正在上传并解析...";
    if (document.querySelector("#streamOutput").value === "true") {
      await runStreamingAnalyze(apiBase, formData);
    } else {
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
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail || data, null, 2)
        );
      }

      setOutputs(data);
      setWorkflowStep(2);
      activateTab("parsed");
      statusText.textContent = "文件解析和五大模块提取完成";
      finishParseTimer();
    }
  } catch (error) {
    finishParseTimer();
    const detail = formatErrorDetail(error, apiBase);
    showResults();
    if (lastParsedSections.length) {
      setWorkflowStep(2);
      activateTab("parsed");
      setParsedSections(lastParsedSections);
      statusText.textContent = "文件解析已完成，但后续分析失败，详情已写入商务内容区";
      renderBusinessContent(detail);
    } else {
      statusText.textContent = "处理失败，详情已写入结果区";
      renderNotice(`其他关键要求：${detail}`);
      renderBusinessContent(detail);
      renderTechnicalContent(detail);
      renderQualification("");
      renderScoring("");
    }
  } finally {
    setLoading(false);
  }
});

async function fetchWithTimeout(url, options = {}, timeoutMs = 10000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

function getApiBase() {
  const input = document.querySelector("#apiBase");
  const value = input?.value?.trim() || "http://127.0.0.1:8000";
  const normalized = value.replace(/\/$/, "");
  if (!/^https?:\/\//i.test(normalized)) {
    return `http://${normalized}`;
  }
  return normalized;
}

async function ensureBackendReady(apiBase) {
  let diagnoseResult = null;
  const hasElectronBackend = Boolean(window.backend?.ensure);
  try {
    if (hasElectronBackend) {
      statusText.textContent = "正在确认后端服务...";
      await window.backend.ensure(apiBase);
    } else {
      statusText.textContent = "正在检测后端连接...";
    }

    statusText.textContent = "正在检测后端连接...";
    const healthResponse = await fetchWithTimeout(`${apiBase}/health`, { method: "GET" }, 12000);
    if (!healthResponse.ok) {
      throw new Error(`后端服务异常：HTTP ${healthResponse.status}`);
    }
  } catch (error) {
    if (window.backend?.diagnose) {
      try {
        diagnoseResult = await window.backend.diagnose(apiBase);
      } catch (diagnoseError) {
        diagnoseResult = {
          error: diagnoseError?.message || String(diagnoseError)
        };
      }
    }

    const logs = Array.isArray(diagnoseResult?.logs)
      ? diagnoseResult.logs.slice(-20).join("\n")
      : "";
    const hint = hasElectronBackend
      ? "Electron 会自动尝试启动 FastAPI；如果仍失败，优先查看下方端口、后端目录和最近日志。"
      : "当前页面没有检测到 Electron 后端桥接，无法自动启动 FastAPI。请用 npm start 启动桌面端，或先手动启动后端。";
    throw new Error(JSON.stringify({
      detail: {
        type: "后端自动检查失败",
        message: error?.message || String(error),
        hint,
        port: diagnoseResult?.port,
        healthy: diagnoseResult?.healthy,
        backend_dir: diagnoseResult?.backendDir,
        owned_process: diagnoseResult?.ownedProcess,
        electron_bridge: hasElectronBackend,
        diagnose_error: diagnoseResult?.error,
        logs
      }
    }, null, 2));
  }
}

async function runStreamingAnalyze(apiBase, formData) {
  const response = await fetch(`${apiBase}/bid-documents/upload-analyze-stream`, {
    method: "POST",
    body: formData
  });

  if (!response.ok || !response.body) {
    const text = await response.text();
    throw new Error(text || `流式接口异常：HTTP ${response.status}`);
  }

  const decoder = new TextDecoder("utf-8");
  const reader = response.body.getReader();
  const buffers = {
    project_overview: "",
    business_content: "",
    technical_scoring_requirements: "",
    qualification_compliance_requirements: "",
    price_scoring_requirements: ""
  };
  let pending = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    pending += decoder.decode(value, { stream: true });
    const lines = pending.split("\n");
    pending = lines.pop() || "";
    lines.filter(Boolean).forEach((line) => {
      const event = JSON.parse(line);
      handleStreamEvent(event, buffers);
    });
  }

  if (pending.trim()) {
    handleStreamEvent(JSON.parse(pending), buffers);
  }
}

async function runStreamingEditedAnalyze(apiBase, payload) {
  const response = await fetch(`${apiBase}/bid-documents/analyze-content-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok || !response.body) {
    const text = await response.text();
    throw new Error(text || `流式接口异常：HTTP ${response.status}`);
  }

  const decoder = new TextDecoder("utf-8");
  const reader = response.body.getReader();
  const buffers = {
    project_overview: "",
    business_content: "",
    technical_scoring_requirements: "",
    qualification_compliance_requirements: "",
    price_scoring_requirements: ""
  };
  let pending = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    pending += decoder.decode(value, { stream: true });
    const lines = pending.split("\n");
    pending = lines.pop() || "";
    lines.filter(Boolean).forEach((line) => {
      const event = JSON.parse(line);
      handleStreamEvent(event, buffers);
    });
  }

  if (pending.trim()) {
    handleStreamEvent(JSON.parse(pending), buffers);
  }
}

function handleStreamEvent(event, buffers) {
  if (event.type === "status") {
    statusText.textContent = event.message || "处理中...";
    return;
  }

  if (event.type === "parsed") {
    if (Array.isArray(event.sections)) {
      lastParsedSections = event.sections;
      setParsedSections(event.sections);
    }
    if (event.parse_method_used) {
      fileName.textContent = `实际解析方案：${PARSE_METHOD_LABELS[event.parse_method_used] || event.parse_method_used}`;
    }
    statusText.textContent = event.message || "文件解析完成，正在调用大模型...";
    return;
  }

  if (event.type === "image_analysis") {
    renderParseQuality(event.parse_quality || null);
    setImageAnalysisDisplay(event.content || "未提取到图片。", event.items || []);
    statusText.textContent = event.message || "图片解析完成";
    return;
  }

  if (event.type === "content_review") {
    renderContentReviewContent(event.content || "内容审查暂无结果");
    statusText.textContent = event.message || "内容审查完成";
    return;
  }

  if (event.type === "chunk") {
    buffers[event.field] = (buffers[event.field] || "") + (event.content || "");
    updateStreamingField(event.field, buffers[event.field]);
    return;
  }

  if (event.type === "field_done") {
    buffers[event.field] = event.content || buffers[event.field] || "";
    updateStreamingField(event.field, buffers[event.field]);
    statusText.textContent = event.message || "当前模块提取完成";
    return;
  }

  if (event.type === "done") {
    setOutputs(event.result || buffers);
    lastAnalysisResult = { ...(event.result || buffers) };
    if (Array.isArray(event.result?.sections)) {
      lastParsedSections = event.result.sections;
    }
    setWorkflowStep(2);
    activateTab("parsed");
    statusText.textContent = event.message || "全部分析完成";
    finishParseTimer();
    return;
  }

  if (event.type === "error") {
    throw new Error(JSON.stringify({ detail: event }, null, 2));
  }
}

function startParseTimer() {
  parseStartTime = performance.now();
  if (parseDuration) {
    parseDuration.textContent = "用时：--";
    parseDuration.classList.add("hidden");
  }
}

function finishParseTimer() {
  if (!parseStartTime || !parseDuration) {
    return;
  }
  const seconds = Math.max(0, Math.round((performance.now() - parseStartTime) / 1000));
  parseDuration.textContent = `用时：${formatDuration(seconds)}`;
  parseDuration.classList.remove("hidden");
  parseStartTime = 0;
}

function formatDuration(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes <= 0) {
    return `${seconds}秒`;
  }
  return `${minutes}分${String(seconds).padStart(2, "0")}秒`;
}

function updateStreamingField(field, value) {
  if (field === "project_overview") {
    renderNotice(value);
  } else if (field === "business_content") {
    renderBusinessContent(value);
  } else if (field === "technical_scoring_requirements") {
    renderTechnicalContent(value);
  } else if (field === "qualification_compliance_requirements") {
    renderQualification(value);
  } else if (field === "price_scoring_requirements") {
    renderScoring(value);
  } else if (field === "content_review_markdown") {
    renderContentReviewContent(value);
  }
}

function activateTab(tabId) {
  document.querySelectorAll(".tab").forEach((item) => {
    item.classList.toggle("active", item.dataset.tab === tabId);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === tabId);
  });
}

function setWorkflowStep(step) {
  const copy = {
    1: {
      kicker: "STEP 01",
      title: "上传招标文件",
      subtitle: `当前解析方案：${PARSE_METHOD_LABELS[parseMethod.value]}`
    },
    2: {
      kicker: "STEP 02",
      title: "招标文件分析核对",
      subtitle: "请核对解析后的招标内容，可修改后重新分析"
    },
    3: {
      kicker: "STEP 03",
      title: "标书生成",
      subtitle: "已完成招标文件核对，后续将在这里生成标书材料"
    }
  }[step];

  stepKicker.textContent = copy.kicker;
  stepTitle.textContent = copy.title;
  fileName.textContent = copy.subtitle;
  document.querySelectorAll(".flow-step").forEach((item) => {
    const itemStep = Number(item.dataset.flowStep);
    item.classList.toggle("active", itemStep === step);
    item.classList.toggle("done", itemStep < step);
  });
  document.querySelectorAll(".flow-line").forEach((line, index) => {
    line.classList.toggle("done", index + 1 < step);
  });
  reviewDoneBtn.classList.toggle("visible", step === 2);
  submitBtn.classList.toggle("hidden", step !== 1);
  generationTopPanel.classList.toggle("visible", step === 3);
}

function setParsedSections(sections) {
  if (!parsedMarkdownOutput) {
    return;
  }
  lastParsedSections = Array.isArray(sections) ? sections : [];
  setImageAnalysisDisplay(sectionsToMarkdown(sections));
}

function sectionsToMarkdown(sections) {
  return (sections || [])
    .map((section) => section.markdown || section.content || "")
    .filter(Boolean)
    .join("\n\n");
}

function collectExtractedForReview() {
  return {
    ...lastAnalysisResult,
    project_overview: getTargetText(noticeFields),
    business_content: getTargetText(businessOutput),
    technical_scoring_requirements: getTargetText(technicalOutput),
    qualification_compliance_requirements: getTargetText(qualificationTables),
    price_scoring_requirements: getTargetText(scoringTables)
  };
}

function setImageAnalysisDisplay(markdown = "", items = []) {
  if (!parsedMarkdownOutput) {
    return;
  }
  parsedMarkdownOutput.dataset.rawText = markdown || "";
  parsedMarkdownOutput.innerHTML = "";

  if (items.length) {
    items.forEach((item) => {
      const card = document.createElement("article");
      card.className = "image-analysis-card";

      const image = document.createElement("img");
      image.src = item.image_data_url || "";
      image.alt = `图片 ${item.index || ""}`;
      image.loading = "lazy";

      const body = document.createElement("div");
      body.className = "image-analysis-body";
      body.innerHTML = `
        <h4>图片 ${escapeHtml(String(item.index || ""))}</h4>
        <p>文件：${escapeHtml(item.file_name || "")}</p>
        <section>
          <strong>OCR文本</strong>
          <pre>${escapeHtml(item.ocr_text || "未识别到文字。")}</pre>
        </section>
        <section>
          <strong>AI备注</strong>
          <pre>${escapeHtml(item.ai_note || "未生成备注。")}</pre>
        </section>
      `;

      card.append(image, body);
      parsedMarkdownOutput.appendChild(card);
    });
    return;
  }

  const pre = document.createElement("pre");
  pre.className = "image-analysis-empty";
  pre.textContent = markdown || "未提取到图片。";
  parsedMarkdownOutput.appendChild(pre);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function clearAnalysisOutputs() {
  renderNotice("");
  renderBusinessContent("");
  renderTechnicalContent("暂无结果");
  renderQualification("");
  renderScoring("");
  renderContentReviewContent("内容审查尚未执行。五大模块提取完成后，可点击“执行审查”。");
}

function formatErrorDetail(error, apiBase) {
  const raw = error?.message || String(error);
  let message = raw;
  let type = "前端请求失败";
  let hint = "先确认后端是否启动、端口是否正确，再检查 MinerU 和大模型 API 的网络连接。";
  const extraLines = [];

  try {
    const parsed = JSON.parse(raw);
    const detail = parsed.detail || parsed;
    if (typeof detail === "string") {
      message = detail;
    } else {
      type = detail.error_type || detail.type || type;
      message = detail.message || message;
      hint = detail.hint || hint;
      if (detail.port) {
        extraLines.push(`端口：${detail.port}`);
      }
      if (typeof detail.healthy === "boolean") {
        extraLines.push(`健康检查：${detail.healthy ? "通过" : "未通过"}`);
      }
      if (detail.backend_dir) {
        extraLines.push(`后端目录：${detail.backend_dir}`);
      }
      if (typeof detail.owned_process === "boolean") {
        extraLines.push(`Electron 托管后端进程：${detail.owned_process ? "是" : "否"}`);
      }
      if (typeof detail.electron_bridge === "boolean") {
        extraLines.push(`Electron 自动启动桥接：${detail.electron_bridge ? "可用" : "不可用"}`);
      }
      if (detail.diagnose_error) {
        extraLines.push(`诊断接口错误：${detail.diagnose_error}`);
      }
      if (detail.logs) {
        extraLines.push("", "最近后端日志：", detail.logs);
      }
      if (detail.traceback) {
        extraLines.push("", "后端 traceback 摘要：", detail.traceback);
      }
    }
  } catch {
    if (raw.includes("Failed to fetch")) {
      type = "无法连接后端";
      message = `浏览器无法访问 ${apiBase}`;
      hint = "检查后端地址和端口是否正确；如果改了端口，要确保 FastAPI 也启动在同一个端口。";
    } else if (raw.includes("aborted") || raw.includes("AbortError")) {
      type = "连接检测超时";
      message = `12 秒内没有连上 ${apiBase}/health`;
      hint = "后端可能没启动，或端口被占用，或本机防火墙/代理拦截。";
    }
  }

  return [
    `错误类型：${type}`,
    `错误信息：${message}`,
    `排查建议：${hint}`,
    ...(extraLines.length ? ["", ...extraLines] : []),
    "",
    "建议排查顺序：",
    "1. 浏览器打开后端地址加 /health，例如 http://127.0.0.1:8000/health，应该返回 {\"status\":\"ok\"}。",
    "2. 如果 /health 不通，先启动后端：python -m uvicorn bid_parser_api:app --host 127.0.0.1 --port 8000。",
    "3. 如果 /health 正常但 MinerU 失败，检查 .env 里的 MINERU_API_TOKEN 和网络代理。",
    "4. 如果 MinerU 正常但大模型失败，检查 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL_ID 或前端选择的模型映射。",
    "5. 大文件解析可能超过 10 分钟，可临时缩小页面范围测试。"
  ].join("\n");
}

function resolveClientParseMethod(file, selectedParseMethod) {
  return selectedParseMethod || "auto";
}

function getMineruModelVersion(selectedParseMethod) {
  if (selectedParseMethod === "mineru_pipeline") {
    return "pipeline";
  }
  if (selectedParseMethod === "mineru_local_pipeline") {
    return "pipeline";
  }
  if (selectedParseMethod === "mineru_html") {
    return "MinerU-HTML";
  }
  return "vlm";
}

function syncMineruOptions() {
  const supportsOptions =
    parseMethod.value === "mineru_vlm" ||
    parseMethod.value === "mineru_pipeline" ||
    parseMethod.value === "mineru_parallel_pages" ||
    parseMethod.value === "mineru_local_pipeline";
  enableFormula.disabled = !supportsOptions;
  enableTable.disabled = !supportsOptions;
  enableFormula.closest(".check-item").classList.toggle("disabled", !supportsOptions);
  enableTable.closest(".check-item").classList.toggle("disabled", !supportsOptions);
}

function syncDeepThinkingOption() {
  const supported = DEEP_THINKING_MODELS.has(llmModel.value);
  enableDeepThinking.disabled = !supported;
  const wrapper = enableDeepThinking.closest(".inline-check, .check-item");
  wrapper.classList.toggle("disabled", !supported);
  wrapper.title = supported
    ? "开启后会要求大模型进行更充分的内部分析，速度可能变慢"
    : "当前模型不支持深度思考";
  if (!supported) {
    enableDeepThinking.checked = false;
  }
}

function syncContentReviewDeepThinkingOption() {
  if (!contentReviewModel || !contentReviewDeepThinking) {
    return;
  }
  const supported = DEEP_THINKING_MODELS.has(contentReviewModel.value);
  contentReviewDeepThinking.disabled = !supported;
  const wrapper = contentReviewDeepThinking.closest(".inline-check, .check-item");
  wrapper?.classList.toggle("disabled", !supported);
  wrapper.title = supported
    ? "内容审查将使用该模型进行更充分的复核，速度可能变慢"
    : "当前审查模型不支持深度思考";
  if (!supported) {
    contentReviewDeepThinking.checked = false;
  }
}

function isDeepThinkingEnabled() {
  return !enableDeepThinking.disabled && enableDeepThinking.checked;
}

function isContentReviewDeepThinkingEnabled() {
  return Boolean(
    contentReviewDeepThinking &&
      !contentReviewDeepThinking.disabled &&
      contentReviewDeepThinking.checked
  );
}

function refreshSubtitle() {
  const file = fileInput.files[0];
  if (stepKicker.textContent === "STEP 01") {
    fileName.textContent = file
      ? `已选择：${file.name}`
      : `当前解析方案：${PARSE_METHOD_LABELS[parseMethod.value]}`;
  }
}

function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  submitBtn.textContent = isLoading ? "处理中..." : "下一步";
  if (isLoading) {
    statusText.textContent = "处理中，文档解析和 LLM 调用可能需要几分钟";
  }
}

function setOutputs(data) {
  lastAnalysisResult = { ...(data || {}) };
  if (Array.isArray(data.sections)) {
    lastParsedSections = data.sections;
  }
  renderNotice(data.project_overview || "");
  renderBusinessContent(data.business_content || "");
  renderTechnicalContent(data.technical_requirements || data.technical_scoring_requirements || "暂无结果");
  renderQualification(data.qualification_compliance_requirements || "");
  renderScoring(data.scoring_requirements || data.price_scoring_requirements || "");
  setImageAnalysisDisplay(data.image_analysis_markdown || "未提取到图片。", data.image_analysis_items || []);
  renderContentReviewContent(data.content_review_markdown || data.content_review_report?.markdown || "内容审查尚未执行。五大模块提取完成后，可点击“执行审查”。");
  renderParseQuality(data.parse_quality || null);
  if (data.parse_method_used) {
    fileName.textContent = `实际解析方案：${PARSE_METHOD_LABELS[data.parse_method_used] || data.parse_method_used}`;
  }
}

function renderParseQuality(quality) {
  if (!parseQuality) {
    return;
  }
  if (!quality) {
    parseQuality.classList.add("hidden");
    parseQuality.innerHTML = "";
    return;
  }

  const warnings = Array.isArray(quality.warnings) && quality.warnings.length
    ? `｜提示：${quality.warnings[0]}`
    : "";
  const profile = quality.preflight_profile || {};
  const pdfType = profile.pdf_type_label ? `<span>PDF类型：${escapeHtml(profile.pdf_type_label)}</span>` : "";
  const parseLayers = Array.isArray(profile.parse_layers) && profile.parse_layers.length
    ? `<span>${escapeHtml(profile.parse_layers.join(" / "))}</span>`
    : "";
  parseQuality.innerHTML = `
    <span>解析质量：${escapeHtml(quality.level || "未知")}</span>
    <span>正文：${escapeHtml(String(quality.text_chars || 0))} 字</span>
    <span>章节：${escapeHtml(String(quality.section_count || 0))}</span>
    <span>图片：${escapeHtml(String(quality.image_count || 0))}</span>
    <span>OCR：${escapeHtml(String(quality.image_ocr_chars || 0))} 字</span>
    ${pdfType}
    ${parseLayers}
    <span>方案：${escapeHtml(quality.parse_method_label || quality.parse_method_used || "")}${escapeHtml(warnings)}</span>
  `;
  parseQuality.classList.remove("hidden");
}

function renderNotice(text) {
  const map = parseKeyValueText(text);
  noticeFields.innerHTML = "";

  NOTICE_FIELDS.forEach(([key, label]) => {
    const field = document.createElement("label");
    field.className = "field-block";
    field.dataset.label = label;
    const title = document.createElement("span");
    title.textContent = label;
    const input = document.createElement("textarea");
    input.readOnly = true;
    input.value = pickValue(map, key) || "";
    input.placeholder = "未提取到";
    field.append(title, input);
    noticeFields.appendChild(field);
  });

  NOTICE_BOOLEAN_FIELDS.forEach(([key, label]) => {
    const field = document.createElement("div");
    field.className = "field-block boolean-field readonly";
    field.dataset.label = label;
    const title = document.createElement("span");
    title.textContent = label;
    const controls = document.createElement("div");
    controls.className = "segmented";
    const current = normalizeYesNo(pickValue(map, key));
    ["是", "否"].forEach((value) => {
      const button = document.createElement("button");
      button.type = "button";
      button.disabled = true;
      button.textContent = value;
      button.dataset.value = value;
      button.classList.toggle("active", current === value);
      controls.appendChild(button);
    });
    field.append(title, controls);
    noticeFields.appendChild(field);
  });
}

function renderQualification(text) {
  renderSelectableTables(qualificationTables, text, [
    {
      title: "资格性审查",
      aliases: ["资格性审查", "资格审查", "资格要求"],
      headers: ["序号", "资格要求", "需提供资料"]
    },
    {
      title: "符合性审查",
      aliases: ["符合性审查", "符合审查", "响应性审查"],
      headers: ["序号", "资格要求", "需提供资料"]
    },
    {
      title: "废标项",
      aliases: ["废标项", "无效投标", "否决项", "否决投标"],
      headers: ["序号", "废标项", "具体表现"]
    }
  ]);
}

function renderScoring(text) {
  renderSelectableTables(scoringTables, text, [
    {
      title: "商务评分",
      aliases: ["商务评分", "商务分", "商务部分", "商务评审", "商务评价", "资信评分", "资信部分", "资信评审", "企业实力", "类似业绩", "项目业绩"],
      headers: ["评分项", "评分标准", "分数"]
    },
    {
      title: "技术评分",
      aliases: ["技术评分", "技术分", "技术部分", "技术评审", "技术评价", "技术方案", "实施方案", "服务方案", "详细评审", "综合评分"],
      headers: ["评分项", "评分标准", "分数"]
    }
  ]);
}

function renderBusinessContent(text) {
  const raw = String(text || "");
  businessOutput.dataset.rawText = raw;
  businessOutput.innerHTML = renderSimpleMarkdown(raw || "暂无结果");
}

function renderTechnicalContent(text) {
  const raw = String(text || "");
  technicalOutput.dataset.rawText = raw;
  technicalOutput.innerHTML = renderSimpleMarkdown(raw || "暂无结果");
}

function renderContentReviewContent(text) {
  const raw = String(text || "");
  contentReviewOutput.dataset.rawText = raw;
  contentReviewOutput.innerHTML = renderSimpleMarkdown(raw || "内容审查暂无结果");
}

function renderSimpleMarkdown(text) {
  const lines = String(text || "").split(/\r?\n/);
  const html = [];
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].trim();
    if (!line) {
      continue;
    }

    const tableLines = [];
    while (
      index < lines.length &&
      lines[index].trim().startsWith("|") &&
      lines[index].trim().endsWith("|")
    ) {
      tableLines.push(lines[index].trim());
      index += 1;
    }
    if (tableLines.length) {
      index -= 1;
      html.push(renderMarkdownTableHtml(tableLines));
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      const level = Math.min(4, heading[1].length + 2);
      html.push(`<h${level}>${escapeHtml(heading[2])}</h${level}>`);
      continue;
    }

    html.push(`<p>${escapeHtml(line)}</p>`);
  }
  return html.join("");
}

function renderMarkdownTableHtml(tableLines) {
  const rows = tableLines
    .filter((line) => !/^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line))
    .map((line) => line.split("|").slice(1, -1).map((cell) => cell.trim()));
  if (!rows.length) {
    return "";
  }

  const [headers, ...bodyRows] = rows;
  const headCells = headers.map((cell) => `<th>${escapeHtml(cell)}</th>`).join("");
  const bodyCells = (bodyRows.length ? bodyRows : [["未提及", ""]])
    .map((row) => `<tr>${headers.map((_, index) => `<td>${escapeHtml(row[index] || "")}</td>`).join("")}</tr>`)
    .join("");
  return `
    <div class="readonly-table-wrap business-table-wrap">
      <table class="readonly-table business-table">
        <thead><tr>${headCells}</tr></thead>
        <tbody>${bodyCells}</tbody>
      </table>
    </div>
  `;
}

function renderSelectableTables(container, text, modules) {
  const tabs = document.querySelector(`[data-module-tabs="${container.id}"]`);
  tabs.innerHTML = "";
  container.innerHTML = "";

  modules.forEach((module, index) => {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.textContent = module.title;
    tab.className = index === 0 ? "active" : "";
    tab.addEventListener("click", () => {
      tabs.querySelectorAll("button").forEach((button) => button.classList.remove("active"));
      container.querySelectorAll(".table-module").forEach((panel) => panel.classList.remove("active"));
      tab.classList.add("active");
      container.querySelector(`[data-module="${module.title}"]`).classList.add("active");
    });
    tabs.appendChild(tab);

    const section = document.createElement("section");
    section.className = `table-module ${index === 0 ? "active" : ""}`;
    section.dataset.module = module.title;
    const rows = extractRowsForModule(text, module);
    section.appendChild(buildReadonlyTable(module.headers, rows));
    container.appendChild(section);
  });
}

function buildReadonlyTable(headers, rows) {
  const wrapper = document.createElement("div");
  wrapper.className = "readonly-table-wrap";
  const table = document.createElement("table");
  table.className = "readonly-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headers.forEach((header) => {
    const th = document.createElement("th");
    th.textContent = header;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);

  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    headers.forEach((_, index) => {
      const td = document.createElement("td");
      td.textContent = row[index] || "";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });

  table.append(thead, tbody);
  wrapper.appendChild(table);
  return wrapper;
}

function extractRowsForModule(text, module) {
  const sectionText = sliceSection(text, module.aliases);
  const markdownRows = parseMarkdownTable(sectionText || text, module.headers);
  if (markdownRows.length) {
    return markdownRows;
  }
  const source = (sectionText || "").trim();
  if (source) {
    const row = Array(module.headers.length).fill("");
    if (module.headers[0] === "序号") {
      row[0] = "1";
      row[1] = source;
    } else {
      row[0] = source;
    }
    return [row];
  }
  return [module.headers.map((_, index) => (index === 0 && module.headers[0] === "序号" ? "1" : "未提及"))];
}

function parseMarkdownTable(text, headers) {
  const lines = String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith("|") && line.endsWith("|"));
  if (lines.length < 2) {
    return [];
  }

  return lines
    .filter((line) => !/^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line))
    .slice(1)
    .map((line) => line.split("|").slice(1, -1).map((cell) => cell.trim()))
    .filter((row) => row.some(Boolean))
    .map((row) => headers.map((_, index) => row[index] || ""));
}

function sliceSection(text, aliases) {
  const source = String(text || "");
  const lines = source.split(/\r?\n/);
  const start = lines.findIndex((line) => aliases.some((alias) => line.includes(alias)));
  if (start < 0) {
    return "";
  }
  let end = lines.length;
  for (let index = start + 1; index < lines.length; index += 1) {
    if (/^\s*#{1,4}\s|\s*[一二三四五六七八九十]+[、.]\s|\s*\d+[、.]\s/.test(lines[index])) {
      end = index;
      break;
    }
  }
  return lines.slice(start, end).join("\n");
}

function parseKeyValueText(text) {
  const map = new Map();
  String(text || "")
    .split(/\r?\n/)
    .forEach((line) => {
      const cleaned = line.replace(/^[\s#*\-・\d.、]+/, "").trim();
      const match = cleaned.match(/^([^：:]{2,60})[：:]\s*(.*)$/);
      if (match) {
        map.set(match[1].trim(), match[2].trim());
      }
    });
  return map;
}

function pickValue(map, label) {
  if (map.has(label)) {
    return map.get(label);
  }
  for (const [key, value] of map.entries()) {
    if (label.includes(key) || key.includes(label)) {
      return value;
    }
  }
  return "";
}

function normalizeYesNo(value) {
  const text = String(value || "");
  if (/^是$|专门|面向|暗标|true/i.test(text)) {
    return "是";
  }
  if (/^否$|不是|非|false/i.test(text)) {
    return "否";
  }
  return "";
}

function showResults() {
  contentCard.classList.add("has-result");
}

function resetView() {
  lastAnalysisResult = {};
  lastParsedSections = [];
  setWorkflowStep(1);
  activateTab("notice");
  statusText.textContent = "等待上传";
  renderParseQuality(null);
  if (parseDuration) {
    parseDuration.textContent = "用时：--";
    parseDuration.classList.add("hidden");
  }
  parseStartTime = 0;
  submitBtn.classList.remove("ready");
  submitBtn.disabled = false;
  submitBtn.textContent = "下一步";
  contentCard.classList.remove("has-result");
  renderNotice("");
  renderBusinessContent("");
  renderTechnicalContent("暂无结果");
  setImageAnalysisDisplay("");
  renderQualification("");
  renderScoring("");
  syncMineruOptions();
  syncDeepThinkingOption();
}

function getTargetText(target) {
  if (!target) {
    return "";
  }
  if ("value" in target) {
    return target.value;
  }
  if (target.dataset?.rawText) {
    return target.dataset.rawText;
  }
  if (target.id === "parsedMarkdownOutput" && target.dataset.rawText) {
    return target.dataset.rawText;
  }
  if (target.id === "noticeFields") {
    return serializeNoticeFields();
  }
  if (target.id === "qualificationTables" || target.id === "scoringTables") {
    return serializeReadonlyTables(target);
  }
  return target.textContent || "";
}

function serializeNoticeFields() {
  const lines = [];
  noticeFields.querySelectorAll(".field-block").forEach((field) => {
    const label = field.dataset.label || "";
    const textarea = field.querySelector("textarea");
    const active = field.querySelector(".segmented .active");
    lines.push(`${label}：${textarea ? textarea.value : active?.dataset.value || ""}`);
  });
  return lines.join("\n");
}

function serializeReadonlyTables(container) {
  const parts = [];
  container.querySelectorAll(".table-module").forEach((module) => {
    const title = module.dataset.module || "";
    const headers = Array.from(module.querySelectorAll("thead th")).map((th) => th.textContent);
    const rows = Array.from(module.querySelectorAll("tbody tr")).map((tr) =>
      Array.from(tr.querySelectorAll("td")).map((td) => td.textContent)
    );
    parts.push(`## ${title}\n| ${headers.join(" | ")} |\n| ${headers.map(() => "---").join(" | ")} |`);
    rows.forEach((row) => {
      parts.push(`| ${row.join(" | ")} |`);
    });
  });
  return parts.join("\n");
}

function openViewer(title, text, target = null) {
  activeViewerTarget = target && "value" in target && !target.readOnly ? target : null;
  viewerTitle.textContent = title;
  viewerText.value = text || "暂无内容";
  const richHtml = buildViewerHtml(target, text);
  if (richHtml) {
    viewerRich.innerHTML = richHtml;
    viewerRich.hidden = false;
    viewerText.hidden = true;
  } else {
    viewerRich.innerHTML = "";
    viewerRich.hidden = true;
    viewerText.hidden = false;
  }
  viewerText.readOnly = !activeViewerTarget || Boolean(richHtml);
  viewerSaveBtn.classList.toggle("hidden", !activeViewerTarget);
  viewerModal.classList.add("open");
  viewerModal.setAttribute("aria-hidden", "false");
  setTimeout(() => (richHtml ? viewerRich.focus() : viewerText.focus()), 0);
}

function closeViewer() {
  activeViewerTarget = null;
  viewerRich.innerHTML = "";
  viewerRich.hidden = true;
  viewerText.hidden = false;
  viewerModal.classList.remove("open");
  viewerModal.setAttribute("aria-hidden", "true");
}

function buildViewerHtml(target, text) {
  if (!target) {
    return "";
  }
  if (target.id === "parsedMarkdownOutput") {
    return target.innerHTML || renderSimpleMarkdown(text || "");
  }
  if (target.id === "qualificationTables" || target.id === "scoringTables") {
    return renderSimpleMarkdown(text || "");
  }
  if (target.classList?.contains("markdown-output")) {
    return renderSimpleMarkdown(text || "");
  }
  return "";
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
syncDeepThinkingOption();
syncContentReviewDeepThinkingOption();
resetView();
