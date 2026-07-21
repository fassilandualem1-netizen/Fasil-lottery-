const tg = window.Telegram?.WebApp;
if (tg) {
    try {
        tg.expand();
        tg.ready();
    } catch (e) {}
}

const initData = tg?.initData || "";
const userId = tg?.initDataUnsafe?.user?.id ? String(tg.initDataUnsafe.user.id) : "999999";

let socket = null;
let currentState = null;

function setBetMessage(message, isError = false) {
    const el = document.getElementById("bet-message");
    el.innerText = message;
    el.style.color = isError ? "#f87171" : "#f59e0b";
}

async function refreshBalance() {
    try {
        const headers = {};
        if (initData) headers["X-Telegram-Init-Data"] = initData;

        const res = await fetch("/api/wallet/balance", { headers });
        const data = await res.json();
        const balanceEl = document.getElementById("balance");
        if (balanceEl) {
            balanceEl.innerText = `${Number(data.balance || 0).toFixed(2)} ETB`;
        }
    } catch (e) {
        console.error(e);
    }
}

async function loadState() {
    try {
        const res = await fetch("/api/aviator/state");
        const data = await res.json();
        currentState = data;
        renderState(data);
    } catch (e) {
        console.error(e);
    }
}

function renderState(data) {
    const statusEl = document.getElementById("game-status");
    const countdownEl = document.getElementById("countdown");
    const multiplierEl = document.getElementById("multiplier");
    const roundEl = document.getElementById("round-id");

    if (!data) return;

    statusEl.innerText = data.status || "WAITING";
    if (data.status === "WAITING") {
        countdownEl.innerText = `Next round in ${Math.max(0, data.time_left || 0)}s`;
    } else if (data.status === "FLYING") {
        countdownEl.innerText = "Round live";
    } else {
        countdownEl.innerText = "Round crashed";
    }

    multiplierEl.innerText = `${Number(data.multiplier || 1).toFixed(2)}x`;
    roundEl.innerText = `Round #${data.round_id || 0}`;

    renderHistory(data.history || []);
}

function renderHistory(history) {
    const list = document.getElementById("history-list");
    if (!history || history.length === 0) {
        list.innerHTML = "<div class='history-item'>No history yet.</div>";
        return;
    }

    list.innerHTML = history.slice(0, 8).map(item => `
        <div class="history-item">
            <div style="display:flex; justify-content:space-between;">
                <span>Crash</span>
                <span>${Number(item).toFixed(2)}x</span>
            </div>
        </div>
    `).join("");
}

function bindSocket() {
    try {
        socket = io();
        socket.on("connect", () => {
            console.log("Socket connected");
        });

        socket.on("game_state", (data) => {
            currentState = data;
            renderState(data);
        });

        socket.on("multiplier_update", (data) => {
            const multiplierEl = document.getElementById("multiplier");
            if (multiplierEl) {
                multiplierEl.innerText = `${Number(data.multiplier || 1).toFixed(2)}x`;
            }
        });

        socket.on("player_cashout", (data) => {
            const activity = document.getElementById("activity-list");
            if (activity) {
                const item = document.createElement("div");
                item.className = "bet-item";
                item.innerHTML = `
                    <div style="display:flex; justify-content:space-between;">
                        <span>Cashout</span>
                        <span>${Number(data.win_amount || 0).toFixed(2)} ETB</span>
                    </div>
                    <div class="small">Multiplier ${Number(data.multiplier || 1).toFixed(2)}x</div>
                `;
                activity.prepend(item);
                while (activity.children.length > 6) activity.removeChild(activity.lastChild);
            }
            refreshBalance();
        });
    } catch (e) {
        console.error(e);
    }
}

async function placeBet() {
    const amount = Number(document.getElementById("bet-amount").value || 0);
    const autoCashout = Number(document.getElementById("auto-cashout").value || 0);

    if (!amount || amount < 10) {
        setBetMessage("Minimum bet is 10 ETB.", true);
        return;
    }

    try {
        const headers = { "Content-Type": "application/json" };
        if (initData) headers["X-Telegram-Init-Data"] = initData;

        const res = await fetch("/api/aviator/bet", {
            method: "POST",
            headers,
            body: JSON.stringify({
                user_id: userId,
                bet_amount: amount,
                auto_cashout: autoCashout
            })
        });

        const data = await res.json();
        setBetMessage(data.message || "Bet placed");
        if (data.status === "success") {
            refreshBalance();
        }
    } catch (e) {
        console.error(e);
        setBetMessage("Could not place bet.", true);
    }
}

async function cashOut() {
    try {
        const headers = {};
        if (initData) headers["X-Telegram-Init-Data"] = initData;

        const res = await fetch("/api/aviator/cashout", {
            method: "POST",
            headers
        });

        const data = await res.json();
        setBetMessage(data.message || "Cashout processed");
        if (data.status === "success") {
            refreshBalance();
        }
    } catch (e) {
        console.error(e);
        setBetMessage("Cashout failed.", true);
    }
}

async function cancelBet() {
    try {
        const headers = {};
        if (initData) headers["X-Telegram-Init-Data"] = initData;

        const res = await fetch("/api/aviator/cancel_bet", {
            method: "POST",
            headers
        });

        const data = await res.json();
        setBetMessage(data.message || "Bet cancelled");
        if (data.status === "success") {
            refreshBalance();
        }
    } catch (e) {
        console.error(e);
        setBetMessage("Cancel failed.", true);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    bindSocket();
    loadState();
    refreshBalance();

    document.getElementById("place-bet-btn").addEventListener("click", placeBet);
    document.getElementById("cashout-btn").addEventListener("click", cashOut);
    document.getElementById("cancel-bet-btn").addEventListener("click", cancelBet);

    document.querySelectorAll(".stake-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const amount = Number(btn.getAttribute("data-amount"));
            document.getElementById("bet-amount").value = amount;
        });
    });

    setInterval(() => {
        loadState();
    }, 1500);
});