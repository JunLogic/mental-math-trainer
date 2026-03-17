const MODE_LABELS = {
  assessment: "Interview Mode",
  training: "Practice Mode",
  zetamac: "Zetamac Mode",
};
const PRESET_OPTIONS = {
  assessment: [
    { value: "interview_default", label: "Interview Default" },
    { value: "interview_balanced", label: "Interview Balanced" },
  ],
  training: [
    { value: "practice_default", label: "Practice Default" },
    { value: "practice_easy", label: "Practice Easy" },
  ],
};
const PRESET_LABELS = Object.fromEntries(
  Object.values(PRESET_OPTIONS).flat().map((preset) => [preset.value, preset.label]),
);

const state = {
  sessionId: null,
  expiresAt: null,
  totalQuestions: 80,
  currentQuestion: null,
  timerHandle: null,
  submitting: false,
  mode: "assessment",
  presetName: "interview_default",
  selectedMode: "assessment",
};

const startScreen = document.getElementById("start-screen");
const gameScreen = document.getElementById("game-screen");
const resultsScreen = document.getElementById("results-screen");
const startButton = document.getElementById("start-button");
const restartButton = document.getElementById("restart-button");
const exitRunButton = document.getElementById("exit-run-button");
const modeInputs = [...document.querySelectorAll('input[name="mode"]')];
const presetControl = document.getElementById("preset-control");
const presetSelect = document.getElementById("preset-select");
const zetamacSettingsPanel = document.getElementById("zetamac-settings");
const modeBadge = document.getElementById("mode-badge");
const presetBadge = document.getElementById("preset-badge");
const timeRemaining = document.getElementById("time-remaining");
const secondaryLabel = document.getElementById("secondary-label");
const secondaryValue = document.getElementById("secondary-value");
const currentScore = document.getElementById("current-score");
const promptEl = document.getElementById("prompt");
const answerForm = document.getElementById("answer-form");
const answerInput = document.getElementById("answer-input");
const submitAnswerButton = document.getElementById("submit-answer");
const optionsEl = document.getElementById("options");
const typedHint = document.getElementById("typed-hint");
const trainingHint = document.getElementById("training-hint");
const typedHintText = document.getElementById("typed-hint-text");
const summaryGrid = document.getElementById("summary-grid");
const operationBody = document.getElementById("operation-body");
const leaderboardBody = document.getElementById("leaderboard-body");
const historyBody = document.getElementById("history-body");
const familyBody = document.getElementById("family-body");
const statusMessage = document.getElementById("status-message");

const zetamacFields = {
  duration: document.getElementById("zetamac-duration"),
  operations: {
    addition: document.getElementById("zetamac-addition-enabled"),
    subtraction: document.getElementById("zetamac-subtraction-enabled"),
    multiplication: document.getElementById("zetamac-multiplication-enabled"),
    division: document.getElementById("zetamac-division-enabled"),
  },
  ranges: {
    addition: {
      leftMin: document.getElementById("zetamac-addition-left-min"),
      leftMax: document.getElementById("zetamac-addition-left-max"),
      rightMin: document.getElementById("zetamac-addition-right-min"),
      rightMax: document.getElementById("zetamac-addition-right-max"),
    },
    subtraction: {
      leftMin: document.getElementById("zetamac-subtraction-left-min"),
      leftMax: document.getElementById("zetamac-subtraction-left-max"),
      rightMin: document.getElementById("zetamac-subtraction-right-min"),
      rightMax: document.getElementById("zetamac-subtraction-right-max"),
    },
    multiplication: {
      leftMin: document.getElementById("zetamac-multiplication-left-min"),
      leftMax: document.getElementById("zetamac-multiplication-left-max"),
      rightMin: document.getElementById("zetamac-multiplication-right-min"),
      rightMax: document.getElementById("zetamac-multiplication-right-max"),
    },
    division: {
      leftMin: document.getElementById("zetamac-division-left-min"),
      leftMax: document.getElementById("zetamac-division-left-max"),
      rightMin: document.getElementById("zetamac-division-right-min"),
      rightMax: document.getElementById("zetamac-division-right-max"),
    },
  },
};

function formatSeconds(totalSeconds) {
  const safe = Math.max(0, totalSeconds);
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function showScreen(name) {
  startScreen.classList.toggle("hidden", name !== "start");
  gameScreen.classList.toggle("hidden", name !== "game");
  resultsScreen.classList.toggle("hidden", name !== "results");
}

function setStatusMessage(message) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("hidden", !message);
}

function clearStatusMessage() {
  setStatusMessage("");
}

function formatResponseSeconds(value) {
  return `${Number(value || 0).toFixed(3).replace(/\.?0+$/, "")}s`;
}

function focusAnswerInput() {
  if (gameScreen.classList.contains("hidden") || answerForm.classList.contains("hidden")) {
    return;
  }

  window.requestAnimationFrame(() => {
    if (!answerInput.disabled && !gameScreen.classList.contains("hidden")) {
      answerInput.focus({ preventScroll: true });
    }
  });
}

function syncPresetOptions() {
  const options = PRESET_OPTIONS[state.selectedMode] || PRESET_OPTIONS.assessment;
  const nextValue = options.some((option) => option.value === presetSelect.value)
    ? presetSelect.value
    : options[0].value;

  presetSelect.innerHTML = "";
  options.forEach((option) => {
    const optionEl = document.createElement("option");
    optionEl.value = option.value;
    optionEl.textContent = option.label;
    presetSelect.appendChild(optionEl);
  });
  presetSelect.value = nextValue;
}

function presetLabel(presetName) {
  return PRESET_LABELS[presetName] || presetName || "-";
}

function getSelectedMode() {
  const checked = modeInputs.find((input) => input.checked);
  return checked ? checked.value : "assessment";
}

function setSelectedMode(mode) {
  state.selectedMode = mode;
  modeInputs.forEach((input) => {
    input.checked = input.value === mode;
  });
}

function syncStartControls() {
  state.selectedMode = getSelectedMode();
  const isZetamac = state.selectedMode === "zetamac";
  presetControl.classList.toggle("hidden", isZetamac);
  zetamacSettingsPanel.classList.toggle("hidden", !isZetamac);
  if (!isZetamac) {
    syncPresetOptions();
  }
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    const detail = errorPayload.detail || "Request failed.";
    throw new Error(detail);
  }

  return response.json();
}

function reportError(error) {
  const message = error.message || "Request failed.";
  if (!gameScreen.classList.contains("hidden")) {
    setStatusMessage(message);
    focusAnswerInput();
    return;
  }
  window.alert(message);
}

function collectZetamacSettings() {
  return {
    duration_seconds: Number(zetamacFields.duration.value),
    operations: {
      addition: zetamacFields.operations.addition.checked,
      subtraction: zetamacFields.operations.subtraction.checked,
      multiplication: zetamacFields.operations.multiplication.checked,
      division: zetamacFields.operations.division.checked,
    },
    ranges: {
      addition: {
        left_min: Number(zetamacFields.ranges.addition.leftMin.value),
        left_max: Number(zetamacFields.ranges.addition.leftMax.value),
        right_min: Number(zetamacFields.ranges.addition.rightMin.value),
        right_max: Number(zetamacFields.ranges.addition.rightMax.value),
      },
      subtraction: {
        left_min: Number(zetamacFields.ranges.subtraction.leftMin.value),
        left_max: Number(zetamacFields.ranges.subtraction.leftMax.value),
        right_min: Number(zetamacFields.ranges.subtraction.rightMin.value),
        right_max: Number(zetamacFields.ranges.subtraction.rightMax.value),
      },
      multiplication: {
        left_min: Number(zetamacFields.ranges.multiplication.leftMin.value),
        left_max: Number(zetamacFields.ranges.multiplication.leftMax.value),
        right_min: Number(zetamacFields.ranges.multiplication.rightMin.value),
        right_max: Number(zetamacFields.ranges.multiplication.rightMax.value),
      },
      division: {
        left_min: Number(zetamacFields.ranges.division.leftMin.value),
        left_max: Number(zetamacFields.ranges.division.leftMax.value),
        right_min: Number(zetamacFields.ranges.division.rightMin.value),
        right_max: Number(zetamacFields.ranges.division.rightMax.value),
      },
    },
  };
}

function resetTransientState() {
  stopTimer();
  state.sessionId = null;
  state.expiresAt = null;
  state.currentQuestion = null;
  state.submitting = false;
  timeRemaining.textContent = "08:00";
  currentScore.textContent = "0";
  secondaryLabel.textContent = "Question";
  secondaryValue.textContent = "1 / 80";
  promptEl.textContent = "17 + 28";
  answerInput.value = "";
  optionsEl.innerHTML = "";
  clearStatusMessage();
}

function updateRunMeta(payload) {
  state.mode = payload.mode;
  state.presetName = payload.settings?.preset_name || state.presetName;
  modeBadge.textContent = payload.mode_label || MODE_LABELS[state.mode] || state.mode;
  if (state.mode === "zetamac") {
    presetBadge.textContent = `${payload.duration_seconds}s`;
  } else {
    presetBadge.textContent = presetLabel(state.presetName);
  }
}

function updateHeader(payload) {
  currentScore.textContent = payload.score;
  if (payload.mode === "zetamac") {
    secondaryLabel.textContent = "Correct / Incorrect";
    secondaryValue.textContent = `${payload.stats.correct} / ${payload.stats.incorrect}`;
    return;
  }

  secondaryLabel.textContent = "Question";
  const question = payload.question;
  if (question) {
    secondaryValue.textContent = `${question.question_number} / ${question.total_questions}`;
  } else {
    secondaryValue.textContent = `${payload.stats.questions_shown} / ${payload.total_questions}`;
  }
}

function setSubmitting(isSubmitting) {
  state.submitting = isSubmitting;
  submitAnswerButton.disabled = isSubmitting;
  answerInput.disabled = isSubmitting;
  exitRunButton.disabled = isSubmitting;
  [...optionsEl.querySelectorAll("button")].forEach((button) => {
    button.disabled = isSubmitting;
  });
  if (!isSubmitting) {
    focusAnswerInput();
  }
}

function stopTimer() {
  clearInterval(state.timerHandle);
  state.timerHandle = null;
}

async function tickTimer() {
  if (!state.expiresAt) {
    return;
  }

  const remaining = Math.max(
    0,
    Math.ceil((new Date(state.expiresAt).getTime() - Date.now()) / 1000),
  );
  timeRemaining.textContent = formatSeconds(remaining);
  if (remaining <= 0) {
    stopTimer();
    await refreshSessionState().catch(() => {});
  }
}

function startTimer(expiresAtIso) {
  state.expiresAt = expiresAtIso;
  if (state.timerHandle !== null) {
    tickTimer().catch(() => {});
    return;
  }

  tickTimer().catch(() => {});
  state.timerHandle = window.setInterval(() => {
    tickTimer().catch(() => {});
  }, 250);
}

function renderOptions(question) {
  optionsEl.innerHTML = "";
  question.options.forEach((optionText, index) => {
    const button = document.createElement("button");
    button.className = "option-button";
    button.type = "button";
    button.textContent = `${index + 1}. ${optionText}`;
    button.disabled = state.submitting;
    button.addEventListener("click", () => submitSessionAnswer({ selected_option_index: index }));
    optionsEl.appendChild(button);
  });
}

function renderQuestion(payload) {
  state.currentQuestion = payload.question;
  clearStatusMessage();
  promptEl.textContent = payload.question.prompt;
  updateHeader(payload);
  updateRunMeta(payload);

  if (payload.mode === "training") {
    answerForm.classList.add("hidden");
    optionsEl.classList.remove("hidden");
    typedHint.classList.add("hidden");
    trainingHint.classList.remove("hidden");
    renderOptions(payload.question);
    return;
  }

  answerForm.classList.remove("hidden");
  answerForm.classList.toggle("answer-form-compact", payload.mode === "zetamac");
  optionsEl.classList.add("hidden");
  optionsEl.innerHTML = "";
  answerInput.value = "";
  answerInput.inputMode = payload.mode === "zetamac" ? "numeric" : "decimal";
  submitAnswerButton.classList.toggle("hidden", payload.mode === "zetamac");
  typedHintText.textContent =
    payload.mode === "zetamac"
      ? "Press Enter to submit. The next problem appears immediately."
      : "Press Enter to submit. The next question appears immediately.";
  typedHint.classList.remove("hidden");
  trainingHint.classList.add("hidden");
}

function summaryCards(summary) {
  const cards = [
    ["Mode", summary.mode_label || MODE_LABELS[summary.mode] || summary.mode],
    ["Final score", summary.score],
    ["Attempted", summary.stats.attempted],
    ["Correct", summary.stats.correct],
    ["Incorrect", summary.stats.incorrect],
    ["Unanswered", summary.stats.unanswered],
    ["Avg response", formatResponseSeconds(summary.stats.average_response_time_seconds)],
    ["Median response", formatResponseSeconds(summary.stats.median_response_time_seconds)],
    ["Fastest", formatResponseSeconds(summary.stats.fastest_response_time_seconds)],
    ["Slowest", formatResponseSeconds(summary.stats.slowest_response_time_seconds)],
  ];

  if (summary.mode === "zetamac") {
    cards.push(["Duration", `${summary.duration_seconds}s`]);
    cards.push(["Operation mix", summary.operation_mix_used]);
  } else {
    cards.push(["Preset", presetLabel(summary.settings?.preset_name)]);
    cards.push(["Accuracy", `${summary.stats.accuracy_percent}%`]);
    cards.push(["Decimal share", `${summary.diagnostics.decimal_share_percent}%`]);
    cards.push(["Missing share", `${summary.diagnostics.missing_variable_share_percent}%`]);
  }

  summaryGrid.innerHTML = "";
  cards.forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "summary-card";
    card.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    summaryGrid.appendChild(card);
  });
}

function renderOperationDiagnostics(items = []) {
  operationBody.innerHTML = "";
  items.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.operation_label}</td>
      <td>${item.attempted}</td>
      <td>${item.accuracy_percent}%</td>
      <td>${formatResponseSeconds(item.average_response_time_seconds)}</td>
    `;
    operationBody.appendChild(row);
  });
}

function renderFamilyDiagnostics(items = []) {
  familyBody.innerHTML = "";
  items.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.family_label}</td>
      <td>${item.shown}</td>
      <td>${item.score}</td>
      <td>${item.correct}</td>
      <td>${item.incorrect}</td>
      <td>${formatResponseSeconds(item.average_response_time_seconds)}</td>
    `;
    familyBody.appendChild(row);
  });
}

function renderHistory(history = []) {
  historyBody.innerHTML = "";
  history.forEach((item) => {
    const row = document.createElement("tr");
    const resultClass =
      item.result === "correct"
        ? "status-correct"
        : item.result === "incorrect"
          ? "status-incorrect"
          : "status-unanswered";
    row.innerHTML = `
      <td>${item.question_number}</td>
      <td>${item.prompt}</td>
      <td>${item.family_label ?? "-"}</td>
      <td>${item.selected_value ?? "-"}</td>
      <td>${item.correct_answer}</td>
      <td class="${resultClass}">${item.result ?? "-"}</td>
      <td>${item.response_time_seconds ?? "-"}</td>
    `;
    historyBody.appendChild(row);
  });
}

function renderLeaderboard(items = []) {
  leaderboardBody.innerHTML = "";
  items.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${new Date(item.timestamp).toLocaleString()}</td>
      <td>${item.mode}</td>
      <td>${item.score}</td>
      <td>${item.correct}</td>
      <td>${item.accuracy_percent}%</td>
      <td>${formatResponseSeconds(item.average_response_time_seconds)}</td>
    `;
    leaderboardBody.appendChild(row);
  });
}

async function loadLeaderboard() {
  const payload = await requestJson("/api/leaderboard");
  renderLeaderboard(payload.items);
}

async function startGame() {
  startButton.disabled = true;
  syncStartControls();
  clearStatusMessage();
  try {
    const payload = await requestJson("/api/game/start", {
      method: "POST",
      body: JSON.stringify(
        state.selectedMode === "zetamac"
          ? {
              mode: "zetamac",
              zetamac_settings: collectZetamacSettings(),
            }
          : {
              mode: state.selectedMode,
              preset_name: presetSelect.value,
            },
      ),
    });
    state.sessionId = payload.session_id;
    state.totalQuestions = payload.total_questions;
    sessionStorage.setItem("mental_math_session_id", state.sessionId);
    showScreen("game");
    startTimer(payload.expires_at);
    renderQuestion(payload);
    setSubmitting(false);
  } catch (error) {
    reportError(error);
  } finally {
    startButton.disabled = false;
  }
}

async function submitSessionAnswer(answerPayload) {
  if (!state.sessionId || state.submitting || !state.currentQuestion) {
    return;
  }

  setSubmitting(true);
  clearStatusMessage();

  try {
    const payload = await requestJson("/api/game/answer", {
      method: "POST",
      body: JSON.stringify({
        session_id: state.sessionId,
        question_number: state.currentQuestion.question_number,
        ...answerPayload,
      }),
    });
    await handleSessionPayload(payload);
  } catch (error) {
    reportError(error);
  } finally {
    setSubmitting(false);
  }
}

async function refreshSessionState() {
  if (!state.sessionId || state.submitting) {
    return;
  }
  const payload = await requestJson(`/api/game/state/${state.sessionId}`);
  await handleSessionPayload(payload);
}

async function abortRun() {
  if (!state.sessionId || state.submitting) {
    return;
  }

  const sessionId = state.sessionId;
  stopTimer();
  try {
    await requestJson("/api/game/abort", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    });
  } catch (error) {
    if (!String(error.message || "").includes("Session not found")) {
      reportError(error);
      return;
    }
  }

  sessionStorage.removeItem("mental_math_session_id");
  resetTransientState();
  showScreen("start");
  await loadLeaderboard();
}

async function handleSessionPayload(payload) {
  updateHeader(payload);
  updateRunMeta(payload);
  currentScore.textContent = payload.score;
  timeRemaining.textContent = formatSeconds(payload.remaining_seconds ?? 0);

  if (payload.finished) {
    stopTimer();
    sessionStorage.removeItem("mental_math_session_id");
    showScreen("results");
    summaryCards(payload);
    renderOperationDiagnostics(payload.diagnostics?.by_operation || []);
    renderFamilyDiagnostics(payload.diagnostics?.by_family || []);
    renderHistory(payload.history || []);
    await loadLeaderboard();
    return;
  }

  showScreen("game");
  startTimer(payload.expires_at);
  renderQuestion(payload);
}

async function restoreSession() {
  const savedSessionId = sessionStorage.getItem("mental_math_session_id");
  if (!savedSessionId) {
    await loadLeaderboard();
    return;
  }

  state.sessionId = savedSessionId;
  try {
    const payload = await requestJson(`/api/game/state/${savedSessionId}`);
    if (payload.finished) {
      sessionStorage.removeItem("mental_math_session_id");
      showScreen("results");
      summaryCards(payload);
      renderOperationDiagnostics(payload.diagnostics?.by_operation || []);
      renderFamilyDiagnostics(payload.diagnostics?.by_family || []);
      renderHistory(payload.history || []);
      await loadLeaderboard();
      return;
    }
    await handleSessionPayload(payload);
  } catch (error) {
    sessionStorage.removeItem("mental_math_session_id");
    state.sessionId = null;
    await loadLeaderboard();
  }
}

answerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const answer = answerInput.value.trim();
  if (!answer) {
    return;
  }
  await submitSessionAnswer({ answer });
});

document.addEventListener("keydown", (event) => {
  if (!gameScreen.classList.contains("hidden") && event.key === "Escape") {
    event.preventDefault();
    abortRun().catch(() => {});
    return;
  }

  if (gameScreen.classList.contains("hidden") || state.submitting || state.mode !== "training") {
    return;
  }

  if (["1", "2", "3", "4"].includes(event.key)) {
    submitSessionAnswer({ selected_option_index: Number(event.key) - 1 });
  }
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    refreshSessionState().catch(() => {});
  }
});

modeInputs.forEach((input) => {
  input.addEventListener("change", syncStartControls);
});
startButton.addEventListener("click", startGame);
exitRunButton.addEventListener("click", () => {
  abortRun().catch(() => {});
});
restartButton.addEventListener("click", async () => {
  resetTransientState();
  summaryGrid.innerHTML = "";
  operationBody.innerHTML = "";
  familyBody.innerHTML = "";
  historyBody.innerHTML = "";
  showScreen("start");
  await loadLeaderboard();
});

setSelectedMode(state.selectedMode);
syncStartControls();
restoreSession().catch(() => {});
