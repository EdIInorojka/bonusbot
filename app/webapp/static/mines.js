(() => {
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  if (tg) {
    tg.ready();
    tg.expand();
    tg.setHeaderColor("#232447");
    tg.setBackgroundColor("#232447");
  }

  const board = document.getElementById("board");
  const multiplierStrip = document.getElementById("multiplierStrip");
  const statusText = document.getElementById("statusText");
  const boardSizeBadge = document.getElementById("boardSizeBadge");
  const mineLimitBadge = document.getElementById("mineLimitBadge");
  const safeCellsPill = document.getElementById("safeCellsPill");
  const mineCellsPill = document.getElementById("mineCellsPill");
  const mineCountInput = document.getElementById("mineCountInput");
  const revealBtn = document.getElementById("revealBtn");
  const resetBtn = document.getElementById("resetBtn");
  const sizeButtons = Array.from(document.querySelectorAll("[data-size]"));
  const minePresetButtons = Array.from(document.querySelectorAll("[data-mine]"));

  const state = {
    size: 5,
    mines: 3,
    revealing: false,
    lastLayout: null,
  };

  const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

  function maxMines(size = state.size) {
    return Math.max(1, size * size - 1);
  }

  function clampMines(value) {
    const parsed = Number.parseInt(String(value || "1"), 10);
    if (Number.isNaN(parsed)) {
      return 1;
    }
    return Math.min(maxMines(), Math.max(1, parsed));
  }

  function shuffle(values) {
    const items = [...values];
    for (let idx = items.length - 1; idx > 0; idx -= 1) {
      const rand = Math.floor(Math.random() * (idx + 1));
      [items[idx], items[rand]] = [items[rand], items[idx]];
    }
    return items;
  }

  function computeMultipliers() {
    const total = state.size * state.size;
    const safe = total - state.mines;
    const chips = [`${state.mines} mines`];
    let multiplier = 1;

    for (let pick = 1; pick <= Math.min(4, safe); pick += 1) {
      const chance = (safe - (pick - 1)) / (total - (pick - 1));
      multiplier *= 1 / chance;
      chips.push(`${Math.max(1, multiplier * 0.96).toFixed(2)}x`);
    }

    while (chips.length < 5) {
      chips.push("1.00x");
    }

    return chips;
  }

  function renderMultipliers() {
    multiplierStrip.innerHTML = "";
    computeMultipliers().forEach((label) => {
      const chip = document.createElement("div");
      chip.className = "multiplier-chip";
      chip.textContent = label;
      multiplierStrip.appendChild(chip);
    });
  }

  function updateMeta() {
    const total = state.size * state.size;
    const safe = total - state.mines;
    boardSizeBadge.textContent = `${state.size}x${state.size}`;
    mineLimitBadge.textContent = `max ${maxMines()}`;
    safeCellsPill.textContent = `Safe ${safe}`;
    mineCellsPill.textContent = `Mines ${state.mines}`;
    mineCountInput.max = String(maxMines());
    mineCountInput.value = String(state.mines);

    sizeButtons.forEach((button) => {
      button.classList.toggle("active", Number.parseInt(button.dataset.size || "0", 10) === state.size);
      button.disabled = state.revealing;
    });

    minePresetButtons.forEach((button) => {
      button.classList.toggle("active", Number.parseInt(button.dataset.mine || "0", 10) === state.mines);
      button.disabled = state.revealing;
    });

    mineCountInput.disabled = state.revealing;
    revealBtn.disabled = state.revealing;
    resetBtn.disabled = state.revealing;

    if (tg && tg.MainButton) {
      tg.MainButton.setParams({
        text: state.revealing ? "GENERATING..." : (state.lastLayout ? "REGENERATE" : "SHOW PREDICTION"),
        is_active: !state.revealing,
        color: "#4de9da",
        text_color: "#06242a",
      });
      tg.MainButton.show();
    }
  }

  function createTile(index) {
    const tile = document.createElement("div");
    tile.className = "tile closed";
    tile.dataset.index = String(index);
    tile.setAttribute("aria-label", `Cell ${index + 1}`);
    board.appendChild(tile);
  }

  function renderBoard() {
    board.innerHTML = "";
    board.style.setProperty("--grid-size", String(state.size));
    board.style.setProperty("--board-gap", state.size >= 9 ? "6px" : state.size >= 7 ? "8px" : "10px");
    board.style.setProperty("--icon-size", state.size >= 9 ? "16px" : state.size >= 7 ? "20px" : state.size >= 5 ? "28px" : "40px");

    for (let index = 0; index < state.size * state.size; index += 1) {
      createTile(index);
    }
  }

  function resetStatus() {
    state.lastLayout = null;
    statusText.textContent = "Closed board ready. Choose the size and mines, then reveal the pattern.";
    renderMultipliers();
    renderBoard();
    updateMeta();
  }

  function revealCell(tile, isMine) {
    tile.classList.remove("closed");
    tile.classList.add("revealed", isMine ? "mine" : "safe");

    const glow = document.createElement("span");
    glow.className = "tile-glow";

    const icon = document.createElement("span");
    icon.className = "tile-icon";
    icon.textContent = isMine ? "💣" : "💎";

    tile.append(glow, icon);
  }

  function buildLayout() {
    const total = state.size * state.size;
    const indexes = Array.from({ length: total }, (_, index) => index);
    const mines = new Set(shuffle(indexes).slice(0, state.mines));
    return { mines, total, safe: total - state.mines };
  }

  async function runPrediction() {
    if (state.revealing) {
      return;
    }

    state.mines = clampMines(mineCountInput.value);
    state.revealing = true;
    state.lastLayout = null;
    statusText.textContent = "Generating a fresh random layout...";
    renderMultipliers();
    renderBoard();
    updateMeta();

    if (tg && tg.HapticFeedback) {
      tg.HapticFeedback.impactOccurred("light");
    }

    const layout = buildLayout();
    const tiles = Array.from(board.children);
    const revealOrder = shuffle(Array.from({ length: tiles.length }, (_, index) => index));
    const delay = state.size >= 9 ? 16 : state.size >= 7 ? 22 : 34;

    for (const tileIndex of revealOrder) {
      revealCell(tiles[tileIndex], layout.mines.has(tileIndex));
      await sleep(delay);
    }

    state.revealing = false;
    state.lastLayout = layout;
    statusText.textContent = `Prediction ready: ${state.size}x${state.size}, ${state.mines} mines, ${layout.safe} safe cells.`;
    updateMeta();

    if (tg && tg.HapticFeedback) {
      tg.HapticFeedback.notificationOccurred("success");
    }
  }

  function applyBoardSize(nextSize) {
    if (state.revealing) {
      return;
    }
    state.size = nextSize;
    state.mines = clampMines(state.mines);
    resetStatus();
  }

  function applyMineCount(nextCount) {
    if (state.revealing) {
      return;
    }
    state.mines = clampMines(nextCount);
    renderMultipliers();
    updateMeta();
    statusText.textContent = `Ready for a ${state.size}x${state.size} board with ${state.mines} mines.`;
  }

  sizeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextSize = Number.parseInt(button.dataset.size || "0", 10);
      if (nextSize > 0) {
        applyBoardSize(nextSize);
      }
    });
  });

  minePresetButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextCount = Number.parseInt(button.dataset.mine || "0", 10);
      if (nextCount > 0) {
        applyMineCount(nextCount);
      }
    });
  });

  mineCountInput.addEventListener("input", () => {
    applyMineCount(mineCountInput.value);
  });

  mineCountInput.addEventListener("blur", () => {
    mineCountInput.value = String(clampMines(mineCountInput.value));
  });

  revealBtn.addEventListener("click", runPrediction);
  resetBtn.addEventListener("click", resetStatus);

  if (tg && tg.MainButton) {
    tg.MainButton.onClick(runPrediction);
  }

  renderMultipliers();
  renderBoard();
  updateMeta();
})();
