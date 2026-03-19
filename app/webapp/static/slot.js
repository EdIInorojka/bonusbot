(() => {
  const tg = window.Telegram.WebApp;
  tg.expand();
  tg.ready();

  const spinBtn = document.getElementById("spinBtn");
  const attemptsLabel = document.getElementById("attemptsLabel");
  const resultText = document.getElementById("resultText");
  const prizeList = document.getElementById("prizeList");
  const reels = [
    document.getElementById("reel1"),
    document.getElementById("reel2"),
    document.getElementById("reel3"),
  ];
  const reelBoxes = reels.map((el) => el.parentElement);

  let attempts = 8;
  let spinNo = 1;
  let symbols = ["🍉", "🍒", "🔔", "🎁", "🍋", "7"];

  const randomSymbol = () => symbols[Math.floor(Math.random() * symbols.length)];

  function updateAttempts() {
    attemptsLabel.textContent = `Spin #${spinNo} | Left: ${attempts}`;
    spinBtn.disabled = attempts <= 0;
  }

  function renderPrizeList(prizes) {
    prizeList.innerHTML = "";
    prizes.forEach((p) => {
      const li = document.createElement("li");
      li.textContent = p;
      prizeList.appendChild(li);
    });
  }

  async function loadConfig() {
    const res = await fetch("/webapp/api/config");
    const cfg = await res.json();
    attempts = cfg.attempts ?? attempts;
    symbols = cfg.symbols ?? symbols;
    if (cfg.button_text) spinBtn.textContent = cfg.button_text;
    if (Array.isArray(cfg.prizes)) renderPrizeList(cfg.prizes);
    updateAttempts();
  }

  function spinAnimation(duration = 1800) {
    reelBoxes.forEach((b) => b.classList.add("spinning"));

    return new Promise((resolve) => {
      const start = Date.now();
      const timer = setInterval(() => {
        reels.forEach((el) => {
          el.textContent = randomSymbol();
        });
        if (Date.now() - start > duration) {
          clearInterval(timer);
          reelBoxes.forEach((b) => b.classList.remove("spinning"));
          resolve();
        }
      }, 80);
    });
  }

  async function makeSpin() {
    if (attempts <= 0) {
      resultText.textContent = "No attempts left";
      return;
    }

    spinBtn.disabled = true;
    await spinAnimation();

    const body = new FormData();
    body.set("init_data", tg.initData);
    body.set("session_key", `${Date.now()}-${Math.random().toString(16).slice(2)}`);

    try {
      const res = await fetch("/webapp/api/spin", { method: "POST", body });
      const data = await res.json();

      if (!res.ok) {
        resultText.textContent = data.detail || "Spin error";
      } else {
        attempts -= 1;
        spinNo += 1;
        updateAttempts();

        const winText = data.won
          ? `🎉 ${data.prize} (+${data.reward_value})`
          : "No win. Try again after cooldown.";

        resultText.textContent = winText;

        if (data.won) {
          reels[0].textContent = "🎁";
          reels[1].textContent = "🎁";
          reels[2].textContent = "🎁";
        }

        try {
          tg.sendData(data.payload_to_bot);
        } catch (e) {
          console.warn("sendData failed", e);
        }
      }
    } catch (e) {
      resultText.textContent = "Network error";
    } finally {
      if (attempts > 0) {
        spinBtn.disabled = false;
      }
    }
  }

  spinBtn.addEventListener("click", makeSpin);
  loadConfig().catch(() => {
    updateAttempts();
  });
})();
