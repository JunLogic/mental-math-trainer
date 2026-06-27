const MODE_LABELS = {
  assessment: "Interview Mode",
  training: "Practice Mode",
  zetamac: "Zetamac Mode",
  zetamac_optimization: "Zetamac Optimization",
};
const TARGET_PACE_BOUNDS = { min: 2.0, max: 6.0 };
const INITIAL_DIFFICULTY_BOUNDS = { min: 0, max: 100 };
const PRESET_OPTIONS = {
  assessment: [
    { value: "interview_default", label: "Interview Default" },
    { value: "interview_balanced", label: "Interview Balanced" },
  ],
  training: [
    { value: "practice_default", label: "Practice Default" },
    { value: "practice_easy", label: "Practice Easy" },
  ],
  zetamac_optimization: [
    { value: "zetamac_optimization_default", label: "Zetamac Optimization" },
  ],
};
const PRESET_LABELS = Object.fromEntries(
  Object.values(PRESET_OPTIONS).flat().map((preset) => [preset.value, preset.label]),
);
const TYPED_AUTO_ADVANCE_MODES = new Set(["assessment", "zetamac", "zetamac_optimization"]);
const INTEGER_INPUT_MODES = new Set(["zetamac", "zetamac_optimization"]);
const WRONG_ANSWER_PENALTY_DELAY_MS = 300;
const KEYPAD_PREFERENCE_KEY = "mental_math_on_screen_keypad";
const NUMERIC_ANSWER_PATTERN = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/;

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
  runSettings: {
    auto_advance_on_correct: false,
    wrong_answer_penalty: false,
    on_screen_keypad: false,
  },
};

const startScreen = document.getElementById("start-screen");
const gameScreen = document.getElementById("game-screen");
const resultsScreen = document.getElementById("results-screen");
const startButton = document.getElementById("start-button");
const restartButton = document.getElementById("restart-button");
const exitRunButton = document.getElementById("exit-run-button");
const exportHistoryButtons = [...document.querySelectorAll(".export-history-button")];
const historyPanelButtons = [...document.querySelectorAll(".history-panel-button")];
const modeInputs = [...document.querySelectorAll('input[name="mode"]')];
const presetControl = document.getElementById("preset-control");
const presetSelect = document.getElementById("preset-select");
const adaptiveEnabledSelect = document.getElementById("adaptive-enabled");
const targetPaceControl = document.getElementById("target-pace-control");
const targetPaceInput = document.getElementById("target-pace");
const initialDifficultyControl = document.getElementById("initial-difficulty-control");
const initialDifficultyInput = document.getElementById("initial-difficulty");
const autoAdvanceControl = document.getElementById("auto-advance-control");
const autoAdvanceCheckbox = document.getElementById("auto-advance-on-correct");
const wrongPenaltyControl = document.getElementById("wrong-penalty-control");
const wrongPenaltyCheckbox = document.getElementById("wrong-answer-penalty");
const wrongPenaltyCopy = document.getElementById("wrong-penalty-copy");
const onScreenKeypadControl = document.getElementById("on-screen-keypad-control");
const onScreenKeypadCheckbox = document.getElementById("on-screen-keypad");
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
const adaptiveResults = document.getElementById("adaptive-results");
const adaptiveGrid = document.getElementById("adaptive-grid");
const operationBody = document.getElementById("operation-body");
const leaderboardBody = document.getElementById("leaderboard-body");
const historyBody = document.getElementById("history-body");
const familyBody = document.getElementById("family-body");
const statusMessage = document.getElementById("status-message");
const penaltyOverlay = document.getElementById("penalty-overlay");
const onScreenKeypadPanel = document.getElementById("on-screen-keypad-panel");
const keypadButtons = [...document.querySelectorAll(".keypad-button")];
const historyPanel = document.getElementById("history-panel");
const historyPanelClose = document.getElementById("history-panel-close");
const historyPanelStatus = document.getElementById("history-panel-status");
const recentHistoryBody = document.getElementById("recent-history-body");

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

function loadKeypadPreference() {
  return localStorage.getItem(KEYPAD_PREFERENCE_KEY) === "on";
}

function saveKeypadPreference(enabled) {
  localStorage.setItem(KEYPAD_PREFERENCE_KEY, enabled ? "on" : "off");
}

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

function formatTimestamp(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value || "-";
  }
  return date.toLocaleString();
}

function formatDifficulty(value) {
  return Number(value || 0).toFixed(1).replace(/\.0$/, "");
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

function supportsAutoAdvance(mode) {
  return TYPED_AUTO_ADVANCE_MODES.has(mode);
}

function supportsTypedInput(mode) {
  return mode !== "training";
}

function keypadEnabledForMode(mode = state.selectedMode) {
  return supportsTypedInput(mode) && onScreenKeypadCheckbox.checked;
}

function autoAdvanceEnabledForMode(mode = state.selectedMode) {
  return supportsAutoAdvance(mode) && autoAdvanceCheckbox.checked;
}

function readGameplaySettings() {
  return {
    auto_advance_on_correct: autoAdvanceEnabledForMode(),
    wrong_answer_penalty: wrongPenaltyCheckbox.checked && !autoAdvanceEnabledForMode(),
  };
}

function syncGameplayControls() {
  const mode = state.selectedMode;
  const autoAdvanceAvailable = supportsAutoAdvance(mode);
  const autoAdvanceEnabled = autoAdvanceEnabledForMode(mode);
  const keypadAvailable = supportsTypedInput(mode);

  autoAdvanceControl.classList.toggle("hidden", !autoAdvanceAvailable);
  onScreenKeypadControl.classList.toggle("hidden", !keypadAvailable);
  wrongPenaltyCheckbox.disabled = autoAdvanceEnabled;
  wrongPenaltyControl.classList.toggle("toggle-disabled", autoAdvanceEnabled);
  if (autoAdvanceEnabled) {
    wrongPenaltyCheckbox.checked = false;
    wrongPenaltyCopy.textContent = "Unavailable while auto-advance on correct answer is enabled.";
  } else {
    wrongPenaltyCopy.textContent = "Flash red and briefly pause after a wrong answer.";
  }
}

function resetPenaltyOverlay() {
  penaltyOverlay.classList.add("hidden");
  penaltyOverlay.classList.remove("active");
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

async function playWrongAnswerPenalty() {
  penaltyOverlay.classList.remove("hidden");
  window.requestAnimationFrame(() => {
    penaltyOverlay.classList.add("active");
  });
  await wait(WRONG_ANSWER_PENALTY_DELAY_MS);
  penaltyOverlay.classList.remove("active");
  await wait(60);
  penaltyOverlay.classList.add("hidden");
}

function normalizeNumericAnswerForComparison(rawValue) {
  const cleaned = String(rawValue || "").trim().replace(/,/g, "").replace(/−/g, "-");
  if (!cleaned || cleaned.endsWith(".") || !NUMERIC_ANSWER_PATTERN.test(cleaned)) {
    return null;
  }

  let sign = "";
  let unsigned = cleaned;
  if (unsigned.startsWith("+") || unsigned.startsWith("-")) {
    sign = unsigned[0] === "-" ? "-" : "";
    unsigned = unsigned.slice(1);
  }

  let [integerPart = "", fractionalPart = ""] = unsigned.split(".");
  integerPart = integerPart.replace(/^0+(?=\d)/, "");
  if (!integerPart) {
    integerPart = "0";
  }
  fractionalPart = fractionalPart.replace(/0+$/, "");
  if (integerPart === "0" && !fractionalPart) {
    sign = "";
  }
  return fractionalPart ? `${sign}${integerPart}.${fractionalPart}` : `${sign}${integerPart}`;
}

function shouldAutoAdvanceCurrentAnswer() {
  if (
    state.submitting
    || !state.currentQuestion
    || !state.runSettings.auto_advance_on_correct
    || !supportsAutoAdvance(state.mode)
  ) {
    return false;
  }

  const expectedAnswer = state.currentQuestion.auto_advance_match_answer;
  if (!expectedAnswer) {
    return false;
  }
  const normalizedInput = normalizeNumericAnswerForComparison(answerInput.value);
  if (normalizedInput === null) {
    return false;
  }
  return normalizedInput === normalizeNumericAnswerForComparison(expectedAnswer);
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

function adaptiveEnabled() {
  return adaptiveEnabledSelect.value === "on";
}

function syncAdaptiveControls() {
  const isEnabled = adaptiveEnabled();
  targetPaceControl.classList.toggle("hidden", !isEnabled);
  initialDifficultyControl.classList.toggle("hidden", !isEnabled);
  targetPaceInput.disabled = !isEnabled;
  initialDifficultyInput.disabled = !isEnabled;
}

function readBoundedNumber(inputEl, { min, max, label }) {
  const raw = String(inputEl.value || "").trim();
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    throw new Error(`${label} must be a number.`);
  }
  if (value < min || value > max) {
    throw new Error(`${label} must be between ${min.toFixed(1)} and ${max.toFixed(1)}.`);
  }
  return value;
}

function collectAdaptiveSettings() {
  const isEnabled = adaptiveEnabled();
  const targetPaceSeconds = isEnabled
    ? readBoundedNumber(targetPaceInput, {
        min: TARGET_PACE_BOUNDS.min,
        max: TARGET_PACE_BOUNDS.max,
        label: "Target pace",
      })
    : Number(targetPaceInput.value || TARGET_PACE_BOUNDS.min);
  const initialDifficulty = isEnabled
    ? readBoundedNumber(initialDifficultyInput, {
        min: INITIAL_DIFFICULTY_BOUNDS.min,
        max: INITIAL_DIFFICULTY_BOUNDS.max,
        label: "Initial difficulty",
      })
    : Number(initialDifficultyInput.value || 40);
  return {
    adaptive_enabled: isEnabled,
    target_pace_seconds: targetPaceSeconds,
    initial_difficulty: initialDifficulty,
  };
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
  syncAdaptiveControls();
  syncGameplayControls();
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
  state.runSettings = {
    auto_advance_on_correct: false,
    wrong_answer_penalty: false,
    on_screen_keypad: keypadEnabledForMode(),
  };
  timeRemaining.textContent = "08:00";
  currentScore.textContent = "0";
  secondaryLabel.textContent = "Question";
  secondaryValue.textContent = "1 / 80";
  promptEl.textContent = "17 + 28";
  answerInput.value = "";
  optionsEl.innerHTML = "";
  onScreenKeypadPanel.classList.add("hidden");
  clearStatusMessage();
  resetPenaltyOverlay();
}

function updateRunMeta(payload) {
  state.mode = payload.mode;
  state.presetName = payload.settings?.preset_name || state.presetName;
  state.runSettings = {
    auto_advance_on_correct: Boolean(payload.settings?.auto_advance_on_correct),
    wrong_answer_penalty: Boolean(payload.settings?.wrong_answer_penalty),
    on_screen_keypad: keypadEnabledForMode(payload.mode),
  };
  modeBadge.textContent = payload.mode_label || MODE_LABELS[state.mode] || state.mode;
  if (state.mode === "zetamac") {
    presetBadge.textContent = `${payload.duration_seconds}s`;
  } else {
    presetBadge.textContent = presetLabel(state.presetName);
  }
}

function updateHeader(payload) {
  currentScore.textContent = payload.score;
  if (INTEGER_INPUT_MODES.has(payload.mode)) {
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
  keypadButtons.forEach((button) => {
    button.disabled = isSubmitting || (button.classList.contains("keypad-decimal") && INTEGER_INPUT_MODES.has(state.mode));
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

function syncKeypadVisibility(mode) {
  const showKeypad = supportsTypedInput(mode) && Boolean(state.runSettings.on_screen_keypad);
  onScreenKeypadPanel.classList.toggle("hidden", !showKeypad);
  const integerOnly = INTEGER_INPUT_MODES.has(mode);
  onScreenKeypadPanel.querySelectorAll(".keypad-decimal").forEach((button) => {
    button.classList.toggle("hidden", integerOnly);
    button.disabled = integerOnly || state.submitting;
  });
}

function renderQuestion(payload) {
  state.currentQuestion = payload.question;
  clearStatusMessage();
  resetPenaltyOverlay();
  promptEl.textContent = payload.question.prompt;
  updateHeader(payload);
  updateRunMeta(payload);

  if (payload.mode === "training") {
    answerForm.classList.add("hidden");
    optionsEl.classList.remove("hidden");
    onScreenKeypadPanel.classList.add("hidden");
    typedHint.classList.add("hidden");
    trainingHint.classList.remove("hidden");
    renderOptions(payload.question);
    return;
  }

  answerForm.classList.remove("hidden");
  answerForm.classList.toggle("answer-form-compact", INTEGER_INPUT_MODES.has(payload.mode));
  optionsEl.classList.add("hidden");
  optionsEl.innerHTML = "";
  answerInput.value = "";
  answerInput.inputMode = INTEGER_INPUT_MODES.has(payload.mode) ? "numeric" : "decimal";
  submitAnswerButton.classList.toggle("hidden", INTEGER_INPUT_MODES.has(payload.mode));
  if (state.runSettings.auto_advance_on_correct) {
    typedHintText.textContent =
      INTEGER_INPUT_MODES.has(payload.mode)
        ? "Correct whole-number answers auto-advance. Press Enter to submit early if needed."
        : "Correct typed answers auto-advance. Press Enter only when you want to force submission.";
  } else {
    typedHintText.textContent =
      INTEGER_INPUT_MODES.has(payload.mode)
        ? "Press Enter to submit. The next problem appears immediately."
        : "Press Enter to submit. The next question appears immediately.";
  }
  syncKeypadVisibility(payload.mode);
  typedHint.classList.remove("hidden");
  trainingHint.classList.add("hidden");
}

function setAnswerInputValue(nextValue) {
  answerInput.value = nextValue;
  answerInput.dispatchEvent(new Event("input", { bubbles: true }));
}

function appendAnswerText(text) {
  const start = answerInput.selectionStart ?? answerInput.value.length;
  const end = answerInput.selectionEnd ?? answerInput.value.length;
  const nextValue = `${answerInput.value.slice(0, start)}${text}${answerInput.value.slice(end)}`;
  setAnswerInputValue(nextValue);
  const nextCaret = start + text.length;
  answerInput.setSelectionRange(nextCaret, nextCaret);
}

function backspaceAnswerText() {
  const start = answerInput.selectionStart ?? answerInput.value.length;
  const end = answerInput.selectionEnd ?? answerInput.value.length;
  if (start !== end) {
    setAnswerInputValue(`${answerInput.value.slice(0, start)}${answerInput.value.slice(end)}`);
    answerInput.setSelectionRange(start, start);
    return;
  }
  if (start <= 0) {
    return;
  }
  const nextValue = `${answerInput.value.slice(0, start - 1)}${answerInput.value.slice(end)}`;
  setAnswerInputValue(nextValue);
  answerInput.setSelectionRange(start - 1, start - 1);
}

function clearAnswerText() {
  setAnswerInputValue("");
  answerInput.focus({ preventScroll: true });
}

async function submitKeypadAnswer() {
  const answer = answerInput.value.trim();
  if (!answer) {
    return;
  }
  await submitSessionAnswer({ answer });
}

function handleKeypadButton(button) {
  if (state.submitting || !state.currentQuestion || !supportsTypedInput(state.mode)) {
    return;
  }

  const action = button.dataset.keypadAction;
  const value = button.dataset.keypadValue;
  if (action === "backspace") {
    backspaceAnswerText();
  } else if (action === "clear") {
    clearAnswerText();
  } else if (action === "submit") {
    submitKeypadAnswer().catch(() => {});
  } else if (value) {
    appendAnswerText(value);
  }
  focusAnswerInput();
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
  } else if (summary.mode === "zetamac_optimization") {
    cards.push(["Preset", presetLabel(summary.settings?.preset_name)]);
    cards.push(["Duration", `${summary.duration_seconds}s`]);
    cards.push(["Operation mix", summary.operation_mix_used]);
    cards.push([
      "Weakness weighting",
      summary.settings?.runtime_generation_policy?.weakness_weighting_applied ? "On" : "Off",
    ]);
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

function renderAdaptiveSummary(adaptive = { enabled: false }) {
  adaptiveGrid.innerHTML = "";
  adaptiveResults.classList.toggle("hidden", !adaptive.enabled);
  if (!adaptive.enabled) {
    return;
  }

  const cards = [
    ["Adaptive Difficulty", "On"],
    ["Initial difficulty", formatDifficulty(adaptive.initial_difficulty)],
    ["Final difficulty", formatDifficulty(adaptive.final_difficulty)],
    ["Peak difficulty", formatDifficulty(adaptive.peak_difficulty)],
    ["Average difficulty", formatDifficulty(adaptive.average_difficulty)],
    ["Target pace", formatResponseSeconds(adaptive.target_pace_seconds)],
    ["Achieved median pace", formatResponseSeconds(adaptive.achieved_median_pace_seconds)],
  ];

  cards.forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "summary-card";
    card.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    adaptiveGrid.appendChild(card);
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
      <td>${formatTimestamp(item.timestamp)}</td>
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

function appendTextCell(row, text) {
  const cell = document.createElement("td");
  cell.textContent = text;
  row.appendChild(cell);
}

function renderRecentHistory(items = []) {
  recentHistoryBody.innerHTML = "";
  if (!items.length) {
    historyPanelStatus.textContent = "No saved runs yet. Finish a run and it will appear here.";
    historyPanelStatus.classList.remove("hidden");
    return;
  }

  historyPanelStatus.classList.add("hidden");
  items.forEach((item) => {
    const row = document.createElement("tr");
    appendTextCell(row, formatTimestamp(item.timestamp));
    appendTextCell(row, item.mode || "-");
    appendTextCell(row, String(item.score ?? 0));
    appendTextCell(row, `${item.accuracy_percent ?? 0}%`);
    appendTextCell(row, formatResponseSeconds(item.average_response_time_seconds));
    recentHistoryBody.appendChild(row);
  });
}

function closeHistoryPanel() {
  historyPanel.classList.add("hidden");
}

async function openHistoryPanel() {
  historyPanel.classList.remove("hidden");
  historyPanelStatus.textContent = "Loading recent runs...";
  historyPanelStatus.classList.remove("hidden");
  recentHistoryBody.innerHTML = "";
  historyPanelButtons.forEach((button) => {
    button.disabled = true;
  });
  try {
    const payload = await requestJson("/api/history/recent?limit=20");
    renderRecentHistory(payload.items || []);
  } catch (error) {
    historyPanelStatus.textContent = error.message || "Unable to load saved runs.";
    historyPanelStatus.classList.remove("hidden");
  } finally {
    historyPanelButtons.forEach((button) => {
      button.disabled = false;
    });
  }
}

function historyExportFilename(date = new Date()) {
  const pad = (value) => String(value).padStart(2, "0");
  const stamp = [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
  ].join("");
  const time = [
    pad(date.getHours()),
    pad(date.getMinutes()),
    pad(date.getSeconds()),
  ].join("");
  return `mental_math_history_${stamp}_${time}.json`;
}

function downloadJson(payload, filename) {
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function exportHistory() {
  exportHistoryButtons.forEach((button) => {
    button.disabled = true;
  });
  try {
    const payload = await requestJson("/api/history/export");
    if (!payload.run_count) {
      window.alert("No saved history to export yet.");
      return;
    }
    downloadJson(payload, historyExportFilename());
  } catch (error) {
    reportError(error);
  } finally {
    exportHistoryButtons.forEach((button) => {
      button.disabled = false;
    });
  }
}

async function startGame() {
  startButton.disabled = true;
  syncStartControls();
  clearStatusMessage();
  try {
    const adaptiveSettings = collectAdaptiveSettings();
    const gameplaySettings = readGameplaySettings();
    const payload = await requestJson("/api/game/start", {
      method: "POST",
      body: JSON.stringify(
        state.selectedMode === "zetamac"
          ? {
              mode: "zetamac",
              ...adaptiveSettings,
              ...gameplaySettings,
              zetamac_settings: collectZetamacSettings(),
            }
          : {
              mode: state.selectedMode,
              preset_name: presetSelect.value,
              ...adaptiveSettings,
              ...gameplaySettings,
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
    if (payload.latest_answer?.result === "incorrect" && state.runSettings.wrong_answer_penalty) {
      await playWrongAnswerPenalty();
    }
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
    renderAdaptiveSummary(payload.adaptive || { enabled: false });
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
      renderAdaptiveSummary(payload.adaptive || { enabled: false });
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

answerInput.addEventListener("input", () => {
  if (!shouldAutoAdvanceCurrentAnswer()) {
    return;
  }
  submitSessionAnswer({ answer: answerInput.value.trim() }).catch(() => {});
});

document.addEventListener("keydown", (event) => {
  if (!historyPanel.classList.contains("hidden") && event.key === "Escape") {
    event.preventDefault();
    closeHistoryPanel();
    return;
  }

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
adaptiveEnabledSelect.addEventListener("change", syncAdaptiveControls);
autoAdvanceCheckbox.addEventListener("change", syncGameplayControls);
wrongPenaltyCheckbox.addEventListener("change", syncGameplayControls);
onScreenKeypadCheckbox.addEventListener("change", () => {
  saveKeypadPreference(onScreenKeypadCheckbox.checked);
  syncGameplayControls();
  syncKeypadVisibility(state.mode);
});
keypadButtons.forEach((button) => {
  button.addEventListener("click", () => handleKeypadButton(button));
});
exportHistoryButtons.forEach((button) => {
  button.addEventListener("click", () => {
    exportHistory().catch(() => {});
  });
});
historyPanelButtons.forEach((button) => {
  button.addEventListener("click", () => {
    openHistoryPanel().catch(() => {});
  });
});
historyPanelClose.addEventListener("click", closeHistoryPanel);
historyPanel.addEventListener("click", (event) => {
  if (event.target === historyPanel) {
    closeHistoryPanel();
  }
});
startButton.addEventListener("click", startGame);
exitRunButton.addEventListener("click", () => {
  abortRun().catch(() => {});
});
restartButton.addEventListener("click", async () => {
  resetTransientState();
  summaryGrid.innerHTML = "";
  adaptiveGrid.innerHTML = "";
  adaptiveResults.classList.add("hidden");
  operationBody.innerHTML = "";
  familyBody.innerHTML = "";
  historyBody.innerHTML = "";
  showScreen("start");
  await loadLeaderboard();
});

onScreenKeypadCheckbox.checked = loadKeypadPreference();
setSelectedMode(state.selectedMode);
syncStartControls();
restoreSession().catch(() => {});
