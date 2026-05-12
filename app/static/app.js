function clampUrls(urls) {
  return urls.slice(0, 20);
}

function updateProcessingStage(stage) {
  const stageOrder = ["ingest", "capture", "extract", "model", "report", "completed"];
  const currentIndex = stageOrder.indexOf(stage);
  document.querySelectorAll(".step-chip").forEach((chip, index) => {
    const chipStage = chip.dataset.stageName;
    const chipIndex = stageOrder.indexOf(chipStage);
    chip.classList.toggle("is-done", currentIndex > chipIndex || stage === "completed");
    chip.classList.toggle("is-active", currentIndex === chipIndex);
  });
}

async function createAnalysisJob(event) {
  event.preventDefault();
  const errorEl = document.getElementById("form-error");
  const submitButton = document.getElementById("submit-button");
  errorEl.textContent = "";

  const rawUrls = document.getElementById("urls").value;
  const urls = clampUrls(
    rawUrls
      .split(/\n|,/)
      .map((value) => value.trim())
      .filter(Boolean),
  );

  if (!urls.length) {
    errorEl.textContent = "Please provide at least one URL.";
    return;
  }

  submitButton.disabled = true;
  submitButton.classList.add("is-loading");

  const payload = {
    urls,
    use_browser: document.getElementById("use_browser").checked,
    offline_only: document.getElementById("offline_only").checked,
  };

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({ detail: "Unable to create job" }));
      errorEl.textContent = data.detail || "Unable to create job";
      submitButton.disabled = false;
      submitButton.classList.remove("is-loading");
      return;
    }

    const data = await response.json();
    window.location.href = `/jobs/${data.job_id}`;
  } catch (error) {
    errorEl.textContent = "Network error while creating job.";
    submitButton.disabled = false;
    submitButton.classList.remove("is-loading");
  }
}

async function pollJobStatus(jobId) {
  const response = await fetch(`/api/jobs/${jobId}`);
  if (!response.ok) {
    return;
  }
  const job = await response.json();
  const statusEl = document.getElementById("job-status");
  const stageEl = document.getElementById("job-stage");
  const msgEl = document.getElementById("job-message");
  const fillEl = document.getElementById("progress-fill");
  const valueEl = document.getElementById("job-progress-value");
  const errorPanel = document.getElementById("job-error-panel");
  const errorText = document.getElementById("job-error-text");

  statusEl.textContent = job.status;
  statusEl.className = `status-badge status-${job.status}`;
  if (job.status === "queued" || job.status === "running") {
    statusEl.innerHTML = `<span class="status-dot"></span>${job.status}`;
  }
  stageEl.textContent = job.stage;
  msgEl.textContent = job.error || job.message;
  fillEl.style.width = `${job.progress}%`;
  valueEl.textContent = `${job.progress}%`;
  updateProcessingStage(job.stage);

  if (job.status === "completed") {
    window.location.href = `/jobs/${jobId}/result`;
    return;
  }

  if (job.status === "failed") {
    errorPanel.classList.remove("hidden");
    errorText.textContent = job.error || job.message || "The job failed.";
    return;
  }

  window.setTimeout(() => pollJobStatus(jobId), 1500);
}

function setupReasonExpanders() {
  document.querySelectorAll("[data-expand-reasons]").forEach((button) => {
    button.addEventListener("click", () => {
      const stack = button.closest("[data-reason-stack]");
      const extra = stack.querySelector(".reason-extra");
      const expanded = !extra.classList.contains("hidden");
      extra.classList.toggle("hidden", expanded);
      button.textContent = expanded ? "Show all reasons" : "Hide extra reasons";
    });
  });
}

function setupScreenshotModal() {
  const modal = document.getElementById("screenshot-modal");
  if (!modal) {
    return;
  }

  const modalImage = document.getElementById("modal-image");
  const modalTitle = document.getElementById("modal-title");
  const closeButton = document.getElementById("modal-close");

  document.querySelectorAll(".screenshot-trigger").forEach((button) => {
    button.addEventListener("click", () => {
      modalImage.src = button.dataset.screenshotUrl;
      modalTitle.textContent = button.dataset.screenshotTitle || "Screenshot Preview";
      modal.classList.remove("hidden");
      modal.setAttribute("aria-hidden", "false");
    });
  });

  function closeModal() {
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
    modalImage.src = "";
  }

  closeButton.addEventListener("click", closeModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      closeModal();
    }
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) {
      closeModal();
    }
  });
}

window.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("analysis-form");
  if (form) {
    form.addEventListener("submit", createAnalysisJob);
  }

  const body = document.body;
  if (body.dataset.page === "processing" && body.dataset.jobId) {
    updateProcessingStage("ingest");
    pollJobStatus(body.dataset.jobId);
  }

  if (body.dataset.page === "result") {
    setupReasonExpanders();
    setupScreenshotModal();
  }
});
