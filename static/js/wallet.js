// Initialize Telegram WebApp
const tg = window.Telegram ? window.Telegram.WebApp : null;
if (tg) {
    tg.expand(); // WebApp ሙሉ ስክሪን እንዲሆን ያደርጋል
    tg.ready();
}

// ለሙከራ (ብሮውዘር ላይ) የምንጠቀምባቸው ነባሪ መረጃዎች
let userId = "12345678";
let userName = "የሰፈር ልጅ";

// ተጠቃሚው በቴሌግራም በኩል ከከፈተው ትክክለኛ መረጃቸውን እንወስዳለን
if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
    userId = tg.initDataUnsafe.user.id.toString();
    userName = tg.initDataUnsafe.user.first_name || tg.initDataUnsafe.user.username || "የሰፈር ልጅ";
}

// App State (የአሁኑ የጨዋታ ሁነታ - Real ወይም Demo)
let gameMode = localStorage.getItem("gameMode") || "real"; 

// የኤለመንቶች ማያያዣ (DOM Elements)
const userDisplayName = document.getElementById("user_display_name");
const userDisplayId = document.getElementById("user_display_id");
const balanceValue = document.getElementById("balance_value");
const modeToggle = document.getElementById("mode_toggle");
const historyList = document.getElementById("history_list");
const leaderboardList = document.getElementById("leaderboard_list");
const dailyBonusBtn = document.getElementById("daily-bonus-btn");

// ፎርሞች (Modals)
const depositModal = document.getElementById("deposit-modal");
const openDepositBtn = document.getElementById("open-deposit");
const closeDepositBtn = document.getElementById("close-deposit");
const depositForm = document.getElementById("deposit-form");

const withdrawModal = document.getElementById("withdraw-modal");
const openWithdrawBtn = document.getElementById("open-withdraw");
const closeWithdrawBtn = document.getElementById("close-withdraw");
const withdrawForm = document.getElementById("withdraw-form");

// የተጠቃሚውን ስምና መታወቂያ በገጹ ላይ ማሳየት
if (userDisplayName) userDisplayName.textContent = userName;
if (userDisplayId) userDisplayId.textContent = userId;

// የ Real/Demo ሞድ ቁልፍን ማደስ
updateModeUI();

// Real vs Demo Mode መቀያየሪያ
if (modeToggle) {
    modeToggle.addEventListener("click", () => {
        gameMode = gameMode === "real" ? "demo" : "real";
        localStorage.setItem("gameMode", gameMode);
        updateModeUI();
        fetchBalance(); // ሞዱ ሲቀየር ባላንሱን እንደገና ያነብባል
    });
}

function updateModeUI() {
    if (!modeToggle) return;
    if (gameMode === "demo") {
        modeToggle.textContent = "DEMO MODE";
        modeToggle.className = "mode-badge demo";
    } else {
        modeToggle.textContent = "REAL MODE";
        modeToggle.className = "mode-badge real";
    }
}

// 1. የባላንስ መረጃ ከ Backend ማምጣት
async function fetchBalance() {
    try {
        const response = await fetch('/api/get_balance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, game_mode: gameMode })
        });
        const data = await response.json();
        if (data.status === "success") {
            balanceValue.textContent = `${parseFloat(data.balance).toFixed(2)} ETB`;
        }
    } catch (error) {
        console.error("Error fetching balance:", error);
    }
}

// 2. የገቢ/ወጪ ታሪክን ማሳየት
async function fetchHistory() {
    try {
        const response = await fetch('/api/get_user_history', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });
        const data = await response.json();
        if (data.status === "success") {
            renderHistory(data.history);
        }
    } catch (error) {
        console.error("Error fetching history:", error);
    }
}

function renderHistory(history) {
    if (!historyList) return;
    if (!history || history.length === 0) {
        historyList.innerHTML = `<p style="text-align: center; color: var(--text-muted); font-size: 0.9rem;">ምንም ታሪክ የለም</p>`;
        return;
    }

    historyList.innerHTML = history.map(item => {
        let statusClass = "pending";
        let statusText = "በሂደት ላይ";
        if (item.status === "completed") {
            statusClass = "completed";
            statusText = "ተጠናቋል";
        } else if (item.status === "refund") {
            statusClass = "failed";
            statusText = "የተመለሰ";
        } else if (item.status === "failed") {
            statusClass = "failed";
            statusText = "የተሰረዘ";
        }

        const sign = (item.type === "ገቢ" || item.type.includes("Win")) ? "+" : "-";
        const dateStr = item.date || "";

        return `
            <div class="history-item">
                <div class="history-details">
                    <p>${item.type}</p>
                    <span>${dateStr}</span>
                </div>
                <div class="history-amount ${statusClass}">
                    ${sign}${parseFloat(item.amount).toFixed(2)} ብር (${statusText})
                </div>
            </div>
        `;
    }).join('');
}

// 3. የሳምንቱ ጀግኖች (Leaderboard) ማምጣት
async function fetchLeaderboard() {
    try {
        const response = await fetch('/api/get_leaderboard', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.status === "success") {
            renderLeaderboard(data.leaders);
        }
    } catch (error) {
        console.error("Error fetching leaderboard:", error);
    }
}

function renderLeaderboard(leaders) {
    if (!leaderboardList) return;
    if (!leaders || leaders.length === 0) {
        leaderboardList.innerHTML = `<p style="text-align: center; color: var(--text-muted); font-size: 0.9rem;">ምንም መረጃ የለም</p>`;
        return;
    }

    leaderboardList.innerHTML = leaders.map((leader, index) => {
        const medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"];
        const rankIcon = medals[index] || `${index + 1}`;
        return `
            <div class="history-item">
                <div class="history-details">
                    <p>${rankIcon} ${leader.user_name}</p>
                    <span>ID: *${leader.user_id.slice(-4)}</span>
                </div>
                <div class="history-amount completed">
                    ${parseFloat(leader.balance).toFixed(2)} ETB
                </div>
            </div>
        `;
    }).join('');
}

// 4. ዕለታዊ ስጦታ (Daily Bonus) መቀበያ
if (dailyBonusBtn) {
    dailyBonusBtn.addEventListener("click", async () => {
        try {
            const response = await fetch('/api/claim_daily', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            });
            const data = await response.json();
            if (data.status === "success") {
                alert(`🎉 እንኳን ደስ አለዎት! የ ${data.gift_amount} ብር ነጻ ስጦታ ወደ እውነተኛ ዋሌትዎ ገብቷል!`);
                fetchBalance();
                fetchHistory();
            } else {
                alert(data.message);
            }
        } catch (error) {
            console.error("Error claiming daily bonus:", error);
            alert("የኔትወርክ ችግር ተከስቷል። እንደገና ይሞክሩ።");
        }
    });
}

// --- ፎርሞችን የመክፈቻና መዝጊያ ሎጂክ ---
if (openDepositBtn) openDepositBtn.addEventListener("click", () => depositModal.style.display = "flex");
if (closeDepositBtn) closeDepositBtn.addEventListener("click", () => depositModal.style.display = "none");

if (openWithdrawBtn) openWithdrawBtn.addEventListener("click", () => withdrawModal.style.display = "flex");
if (closeWithdrawBtn) closeWithdrawBtn.addEventListener("click", () => withdrawModal.style.display = "none");

// ከፎርሙ ውጪ ሲነካ እንዲዘጋ ማድረግ
window.addEventListener("click", (e) => {
    if (e.target === depositModal) depositModal.style.display = "none";
    if (e.target === withdrawModal) withdrawModal.style.display = "none";
});

// 5. የብር ማስገቢያ (Deposit) ጥያቄ መላኪያ
if (depositForm) {
    depositForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const amount = document.getElementById("deposit_amount").value;
        const receiptFile = document.getElementById("deposit_receipt").files[0];

        if (!amount || !receiptFile) {
            alert("እባክዎ ሁሉንም መረጃዎች ያስገቡ!");
            return;
        }

        const formData = new FormData();
        formData.append("user_id", userId);
        formData.append("user_name", userName);
        formData.append("amount", amount);
        formData.append("receipt", receiptFile);

        try {
            const response = await fetch('/api/deposit', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (data.status === "success") {
                alert("✅ የገቢ ጥያቄዎ ለአድሚን ተልኳል። ሲጸድቅ በቦቱ መልዕክት ይደርስዎታል።");
                depositModal.style.display = "none";
                depositForm.reset();
                fetchHistory();
            } else {
                alert(`ስህተት፡ ${data.message}`);
            }
        } catch (error) {
            console.error("Deposit submission error:", error);
            alert("ጥያቄውን መላክ አልተቻለም። እባክዎ እንደገና ይሞክሩ።");
        }
    });
}

// 6. የብር ማውጫ (Withdraw) ጥያቄ መላኪያ
if (withdrawForm) {
    withdrawForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const bankName = document.getElementById("withdraw_bank").value;
        const accountName = document.getElementById("withdraw_name").value;
        const accountNum = document.getElementById("withdraw_account").value;
        const amount = document.getElementById("withdraw_amount").value;

        try {
            const response = await fetch('/api/withdraw', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    user_name: userName,
                    bank_name: bankName,
                    account_name: accountName,
                    phone: accountNum,
                    amount: parseFloat(amount)
                })
            });
            const data = await response.json();
            if (data.status === "success") {
                alert("✅ የወጪ ጥያቄዎ በተሳካ ሁኔታ ቀርቧል። አድሚኑ ሲከፍልዎት በቦቱ ማሳወቂያ ይደርስዎታል።");
                withdrawModal.style.display = "none";
                withdrawForm.reset();
                fetchBalance();
                fetchHistory();
            } else {
                alert(`ስህተት፡ ${data.message}`);
            }
        } catch (error) {
            console.error("Withdraw submission error:", error);
            alert("ጥያቄውን መላክ አልተቻለም። እባክዎ እንደገና ይሞክሩ።");
        }
    });
}

// ገጹ ሲከፈት መረጃዎችን በራስ-ሰር መጫኛ
fetchBalance();
fetchHistory();
fetchLeaderboard();
