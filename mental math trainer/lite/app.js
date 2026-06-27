const BEST_SCORE_KEY = "zetamac_lite_best_score";
const RUN_LOG_KEY = "zetamac_lite_recent_runs";
const OPERATIONS = {
  addition: {
    label: "+",
    make() {
      const left = randomInt(10, 99);
      const right = randomInt(10, 99);
      return { prompt: `${left} + ${right}`, answer: left + right };
    },
  },
  subtraction: {
    label: "-",
    make() {
      const answer = randomInt(2, 99);
      const right = randomInt(2, 99);
      const left = answer + right;
      return { prompt: `${left} - ${right}`, answer };
    },
  },
  multiplication: {
    label: "×",
    make() {
      const left = randomInt(2, 12);
      const right = randomInt(2, 12);
      return { prompt: `${left} × ${right}`, answer: left * right };
    },
  },
  division: {
    label: "÷",
    make() {
      const answer = randomInt(2, 12);
      const divisor = randomInt(2, 12);
      return { prompt: `${answer * divisor} ÷ ${divisor}`, answer };
    },
  },
};

const state = {
  durationSeconds: 120,
  activeOperations: ["addition", "subtraction", "multiplication", "division"],
  running: false,
  endsAt: 0,
  timer: null,
  currentQuestion: null,
  answerText: "",
  score: 0,
  misses: 0,
  streak: 0,
  bestStreak: 0,
};

const screens = {
  start: document.getElementById("start-screen"),
  game: document.getElementById("game-screen"),
  results: document.getElementById("results-screen"),
};
const startButton = document.getElementById("start-button");
const againButton = document.getElementById("again-button");
const settingsButton = document.getElementById("settings-button");
const durationButtons = [...document.querySelectorAll("[data-duration]")];
const operationInputs = [...document.querySelectorAll("[data-operation]")];
const keypadButtons = [...document.querySelectorAll(".keypad button")];
const bestScoreEl = document.getElementById("best-score");
const timeDisplay = document.getElementById("time-display");
const scoreDisplay = document.getElementById("score-display");
const streakDisplay = document.getElementById("streak-display");
const problemDisplay = document.getElementById("problem-display");
const answerDisplay = document.getElementById("answer-display");
const feedback = document.getElementById("feedback");
const resultScore = document.getElementById("result-score");
const resultCopy = document.getElementById("result-copy");
const resultCorrect = document.getElementById("result-correct");
const resultMisses = document.getElementById("result-misses");
const resultBestStreak = document.getElementById("result-best-streak");
const resultDuration = document.getElementById("result-duration");

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function showScreen(name) {
  Object.entries(screens).forEach(([screenName, element]) => {
    element.classList.toggle("hidden", screenName !== name);
  });
}

function formatTime(seconds) {
  const safe = Math.max(0, seconds);
  const minutes = Math.floor(safe / 60);
  const rest = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function normalizeAnswer(value) {
  const cleaned = String(value || "").trim().replace(/,/g, "");
  if (!cleaned || cleaned === "-" || cleaned.endsWith(".")) {
    return null;
  }
  const numeric = Number(cleaned);
  if (!Number.isFinite(numeric)) {
    return null;
  }
  return String(numeric);
}

function loadBestScore() {
  const best = Number(localStorage.getItem(BEST_SCORE_KEY) || "0");
  bestScoreEl.textContent = `Best score: ${best}`;
  return best;
}

function saveRunLog(run) {
  const current = JSON.parse(localStorage.getItem(RUN_LOG_KEY) || "[]");
  current.unshift(run);
  localStorage.setItem(RUN_LOG_KEY, JSON.stringify(current.slice(0, 20)));
}

function selectedOperations() {
  const operations = operationInputs
    .filter((input) => input.checked)
    .map((input) => input.dataset.operation)
    .filter((operation) => Object.prototype.hasOwnProperty.call(OPERATIONS, operation));
  return operations.length ? operations : ["addition"];
}

function makeQuestion() {
  const operation = state.activeOperations[randomInt(0, state.activeOperations.length - 1)];
  return { operation, ...OPERATIONS[operation].make() };
}

function renderHud() {
  scoreDisplay.textContent = state.score;
  streakDisplay.textContent = state.streak;
}

function renderAnswer() {
  answerDisplay.textContent = state.answerText || "0";
}

function nextQuestion() {
  state.currentQuestion = makeQuestion();
  state.answerText = "";
  problemDisplay.textContent = state.currentQuestion.prompt;
  feedback.textContent = "Keep the rhythm.";
  feedback.classList.remove("bad");
  renderAnswer();
}

function remainingSeconds() {
  return Math.max(0, Math.ceil((state.endsAt - Date.now()) / 1000));
}

function tick() {
  const remaining = remainingSeconds();
  timeDisplay.textContent = formatTime(remaining);
  if (remaining <= 0) {
    finishRun();
  }
}

function startRun() {
  state.durationSeconds = Number(document.querySelector(".segment.active")?.dataset.duration || "120");
  state.activeOperations = selectedOperations();
  state.running = true;
  state.endsAt = Date.now() + state.durationSeconds * 1000;
  state.score = 0;
  state.misses = 0;
  state.streak = 0;
  state.bestStreak = 0;
  renderHud();
  timeDisplay.textContent = formatTime(state.durationSeconds);
  showScreen("game");
  nextQuestion();
  clearInterval(state.timer);
  state.timer = window.setInterval(tick, 150);
  tick();
}

function finishRun() {
  if (!state.running) {
    return;
  }

  state.running = false;
  clearInterval(state.timer);
  state.timer = null;
  const previousBest = loadBestScore();
  if (state.score > previousBest) {
    localStorage.setItem(BEST_SCORE_KEY, String(state.score));
    bestScoreEl.textContent = `Best score: ${state.score}`;
  }
  saveRunLog({
    timestamp: new Date().toISOString(),
    duration_seconds: state.durationSeconds,
    score: state.score,
    misses: state.misses,
    best_streak: state.bestStreak,
    operations: state.activeOperations,
  });

  resultScore.textContent = String(state.score);
  resultCorrect.textContent = String(state.score);
  resultMisses.textContent = String(state.misses);
  resultBestStreak.textContent = String(state.bestStreak);
  resultDuration.textContent = `${state.durationSeconds}s`;
  resultCopy.textContent = state.score > previousBest ? "New local best." : "Run saved locally on this device.";
  showScreen("results");
}

function appendKey(value) {
  if (!state.running) {
    return;
  }
  if (value === "-" && state.answerText.includes("-")) {
    return;
  }
  if (value === "-" && state.answerText.length > 0) {
    state.answerText = `-${state.answerText}`;
  } else if (value === "." && state.answerText.includes(".")) {
    return;
  } else {
    state.answerText += value;
  }
  renderAnswer();
  maybeAutoAdvance();
}

function backspace() {
  state.answerText = state.answerText.slice(0, -1);
  renderAnswer();
}

function clearAnswer() {
  state.answerText = "";
  renderAnswer();
}

function maybeAutoAdvance() {
  if (!state.currentQuestion) {
    return;
  }
  const submitted = normalizeAnswer(state.answerText);
  if (submitted === null) {
    return;
  }
  if (submitted === String(state.currentQuestion.answer)) {
    markCorrect();
  }
}

function submitAnswer() {
  if (!state.running || !state.currentQuestion || !state.answerText) {
    return;
  }
  const submitted = normalizeAnswer(state.answerText);
  if (submitted === String(state.currentQuestion.answer)) {
    markCorrect();
    return;
  }
  state.misses += 1;
  state.streak = 0;
  feedback.textContent = `Missed: ${state.currentQuestion.prompt} = ${state.currentQuestion.answer}`;
  feedback.classList.add("bad");
  renderHud();
  window.setTimeout(() => {
    if (state.running) {
      nextQuestion();
    }
  }, 140);
}

function markCorrect() {
  state.score += 1;
  state.streak += 1;
  state.bestStreak = Math.max(state.bestStreak, state.streak);
  renderHud();
  nextQuestion();
}

function handleKeypad(button) {
  const action = button.dataset.action;
  if (action === "backspace") {
    backspace();
  } else if (action === "clear") {
    clearAnswer();
  } else if (action === "submit") {
    submitAnswer();
  } else if (button.dataset.key) {
    appendKey(button.dataset.key);
  }
}

durationButtons.forEach((button) => {
  button.addEventListener("click", () => {
    durationButtons.forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
  });
});

keypadButtons.forEach((button) => {
  button.addEventListener("click", () => handleKeypad(button));
});

document.addEventListener("keydown", (event) => {
  if (!state.running) {
    return;
  }
  if (/^\d$/.test(event.key) || event.key === "." || event.key === "-") {
    event.preventDefault();
    appendKey(event.key);
  } else if (event.key === "Backspace") {
    event.preventDefault();
    backspace();
  } else if (event.key === "Enter") {
    event.preventDefault();
    submitAnswer();
  } else if (event.key === "Escape") {
    event.preventDefault();
    finishRun();
  }
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden && state.running) {
    tick();
  }
});

startButton.addEventListener("click", startRun);
againButton.addEventListener("click", startRun);
settingsButton.addEventListener("click", () => {
  showScreen("start");
});

loadBestScore();
showScreen("start");

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  });
}
