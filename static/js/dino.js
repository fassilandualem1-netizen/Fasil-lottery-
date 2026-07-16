const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const multiplierDisplay = document.getElementById("multiplierDisplay");
const statusText = document.getElementById("statusText");
const historyBar = document.getElementById("historyBar");
const balanceDisplay = document.getElementById('balanceDisplay');

const tg = window.Telegram ? window.Telegram.WebApp : null;
const userId = tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id.toString() : "8488592165";

// 🎮 የጨዋታ State Management
let gameState = 'WAITING'; // WAITING, FLYING, CRASHED
let multiplier = 1.00;
let crashPoint = 1.00;
let countdownTimer = 10;
let crashHistory = [1.28, 2.68, 1.44, 4.36, 2.02, 1.91, 31.23]; // መነሻ (ሰርቨሩ እስኪመልስ)

// ✈️ የአውሮፕላን ምስል (SVG Icon)
const planeImg = new Image();
planeImg.src = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA1MTIgNTEyIj48cGF0aCBmaWxsPSIjZTUwYjJjIiBkPSJNNDQ4IDMzNmMtMTYuNyAwLTMyLTEzLjMtMzItMzJWMjI0SDI4OEwxNTEuNiAzODMuMWMtNi44IDgtMTYuNyAxMi45LTI3LjQgMTIuOUg2NGMtMTUu1IDAtMjUuMS0xNC41LTE5LjktMjguN0w5NiAyMjRIMzJjLTE3LjcgMC0zMi0xNC4zLTMyLTMyczE0LjMtMzIgMzItMzJoNjRsLTUxLjktMTQzLjNDMzguOSAyLjUgNTMuNC03LjUgNjguNi03LjVoNjAuMmMxMC43IDAgMjAuNiA0LjkgMjcuNCAxMi45TDI4OCAxNjBoMTI4di04MGMwLTE4LjcgMTUuMy0zMiAzMi0zMnMzMiAxMy4zIDMyIDMydjIyNGMwIDE4LjctMTUuMyAzMi0zMiAzMnoiLz48L3N2Zy4=";

// 💸 የውርርድ (Dual Bet) State
let bets = {
    1: { state: 'IDLE', amount: 20, isAuto: false }, 
    2: { state: 'IDLE', amount: 20, isAuto: false }
};

// 1. ልክ ሲከፈት ትክክለኛውን ባላንስ ከሰርቨር ማምጣት
async function fetchInitialBalance() {
    try {
        const response = await fetch('/api/get_balance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });
        const result = await response.json();
        if (result.status === "success" && balanceDisplay) {
            balanceDisplay.innerText = result.balance.toFixed(2);
        } else if (balanceDisplay) {
            balanceDisplay.innerText = "0.00";
        }
    } catch (e) {
        console.error("Balance fetch error:", e);
        if(balanceDisplay) balanceDisplay.innerText = "0.00";
    }
}
fetchInitialBalance();

// 🦖 2. ልክ ሲከፈት ቋሚውን የዲኖ ታሪክ ከRedis ማምጣት (አዲሱ API)
async function loadRealHistory() {
    try {
        const response = await fetch('/api/get_history'); // Back-end ላይ የሰራነው አዲሱ GET Route
        const result = await response.json();
        if (result.status === "success") {
            crashHistory = result.history_data;
            renderHistory();
        }
    } catch (e) {
        console.error("History fetch error:", e);
    }
}
loadRealHistory();

function generateCrashPoint() {
    let rand = Math.random();
    if (rand < 0.05) return 1.00; // Instant crash
    return 1.05 + (0.95 / (Math.random() + 0.01));
}

// 🔊 የድምፅ ማጫወቻ
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
function playSound(type) {
    if(audioCtx.state === 'suspended') audioCtx.resume();
    try {
        let osc = audioCtx.createOscillator();
        let gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);

        if (type === "fly") {
            osc.type = "sine";
            osc.frequency.setValueAtTime(80 + (multiplier * 5), audioCtx.currentTime);
            gain.gain.setValueAtTime(0.01, audioCtx.currentTime);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.1);
        } else if (type === "win") {
            osc.type = "sine";
            osc.frequency.setValueAtTime(600, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(1500, audioCtx.currentTime + 0.3);
            gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.4);
        } else if (type === "crash") {
            osc.type = "sawtooth";
            osc.frequency.setValueAtTime(150, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(40, audioCtx.currentTime + 0.5);
            gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.5);
        }
    } catch (e) {}
}

// ================= UI INPUT LOGIC =================
function switchTab(panelId, mode) {
    let bet = bets[panelId];
    if (bet.state !== 'IDLE' && bet.state !== 'QUEUED') return;

    document.getElementById(`tabBet${panelId}`).classList.remove('active');
    document.getElementById(`tabAuto${panelId}`).classList.remove('active');
    
    if (mode === 'auto') {
        document.getElementById(`tabAuto${panelId}`).classList.add('active');
        document.getElementById(`autoSection${panelId}`).style.display = 'flex';
        bet.isAuto = true;
    } else {
        document.getElementById(`tabBet${panelId}`).classList.add('active');
        document.getElementById(`autoSection${panelId}`).style.display = 'none';
        bet.isAuto = false;
    }
}

function updateInputUI() {
    document.getElementById("betInput1").value = bets[1].amount;
    document.getElementById("betInput2").value = bets[2].amount;
}

function adjustBet(panelId, amount) {
    if (bets[panelId].state !== 'IDLE' && bets[panelId].state !== 'QUEUED') return;
    let newVal = bets[panelId].amount + amount;
    if (newVal >= 2) {
        bets[panelId].amount = newVal;
        updateInputUI();
        syncButtons();
    }
}

function setBet(panelId, amount) {
    if (bets[panelId].state !== 'IDLE' && bets[panelId].state !== 'QUEUED') return;
    bets[panelId].amount = amount;
    updateInputUI();
    syncButtons();
}

// ================= HISTORY LOGIC (ቀለማቱ የተስተካከለበት) =================
function renderHistory() {
    historyBar.innerHTML = crashHistory.map(m => {
        let colorClass = 'color-blue'; // ከ 2.0 በታች ሰማያዊ
        if (m >= 10.0) {
            colorClass = 'color-pink'; // ከ 10.0 በላይ ሮዝ/ቀይ
        } else if (m >= 2.0) {
            colorClass = 'color-purple'; // ከ 2.0 እስከ 10.0 ሐምራዊ
        }
        return `<div class="history-chip ${colorClass}">${m.toFixed(2)}x</div>`;
    }).join('');
    historyBar.scrollLeft = 0;
}
renderHistory();

// ================= API & BUTTON ACTION LOGIC =================
async function placeBetAPI(panelId) {
    let bet = bets[panelId];
    try {
        const response = await fetch('/api/dino/bet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, bet_amount: bet.amount })
        });
        const result = await response.json();
        if (result.status === "success") {
            bet.state = 'WAITING';
            if (balanceDisplay) balanceDisplay.innerText = result.new_balance.toFixed(2);
            syncButtons();
        } else {
            alert(result.message || "በቂ ሂሳብ የሎትም!");
            bet.state = 'IDLE';
            syncButtons();
        }
    } catch (e) { console.error(e); }
}

async function executeCashout(panelId) {
    let bet = bets[panelId];
    if (bet.state !== 'IN_GAME') return;

    let currentMult = multiplier; 
    bet.state = 'CASHED_OUT';
    playSound("win");
    
    // ፓነሉ በአረንጓዴ እንዲያሸበርቅ
    let btn = document.getElementById(`btnAction${panelId}`);
    btn.className = "action-btn btn-bet"; 
    btn.style.backgroundColor = "#28a745"; 

    try {
        const response = await fetch('/api/dino/cashout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, bet_amount: bet.amount, multiplier: currentMult })
        });
        const result = await response.json();
        if (result.status === "success") {
            if (balanceDisplay) balanceDisplay.innerText = result.new_balance.toFixed(2);
            btn.innerHTML = `WIN <div class="btn-subtext">${result.win_amount.toFixed(2)} ETB</div>`;
        }
    } catch (e) { console.error(e); }
}

function handleAction(panelId) {
    let bet = bets[panelId];

    if (bet.state === 'IDLE') {
        if(gameState === 'FLYING') {
            bet.state = 'QUEUED';
            syncButtons();
        } else if (gameState === 'WAITING') {
            placeBetAPI(panelId);
        }
    } 
    else if (bet.state === 'QUEUED') {
        bet.state = 'IDLE';
        syncButtons();
    }
    else if (bet.state === 'IN_GAME') {
        executeCashout(panelId);
    }
}

function syncButtons() {
    [1, 2].forEach(id => {
        let bet = bets[id];
        let btn = document.getElementById(`btnAction${id}`);
        let inputField = document.getElementById(`betInput${id}`);

        if (bet.state === 'IDLE') {
            btn.className = "action-btn btn-bet";
            btn.style.backgroundColor = "#28a745"; // አረንጓዴ
            btn.innerHTML = `BET <div class="btn-subtext">${bet.amount.toFixed(2)} ETB</div>`;
            inputField.disabled = false;
        } 
        else if (bet.state === 'QUEUED') {
            btn.className = "action-btn btn-cancel";
            btn.innerHTML = `CANCEL <div class="btn-subtext">Waiting next round</div>`;
            inputField.disabled = true;
        }
        else if (bet.state === 'WAITING') {
            btn.className = "action-btn btn-cancel";
            btn.innerHTML = `WAITING... <div class="btn-subtext">Bet Placed</div>`;
            inputField.disabled = true;
        }
        else if (bet.state === 'IN_GAME') {
            btn.className = "action-btn btn-cashout";
            btn.style.backgroundColor = "#ff9800"; // ብርቱካናማ ለካሽአውት
            let winAmount = (bet.amount * multiplier).toFixed(2);
            btn.innerHTML = `CASH OUT <div class="btn-subtext">${winAmount} ETB</div>`;
            inputField.disabled = true;
        }
        else if (bet.state === 'CRASHED') {
            btn.className = "action-btn btn-disabled";
            btn.style.backgroundColor = "#555"; // ግራጫ
            btn.innerHTML = `CRASHED <div class="btn-subtext">- ${bet.amount.toFixed(2)} ETB</div>`;
            inputField.disabled = true;
        }
    });
}

// ================= CANVAS ANIMATION LOGIC =================
let sunburstAngle = 0;
let planePos = { x: 0, y: 500 };

function drawSunburst() {
    ctx.save();
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate(sunburstAngle);
    const rays = 24;
    for (let i = 0; i < rays; i++) {
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.arc(0, 0, canvas.width, (i * 2 * Math.PI) / rays, ((i + 0.5) * 2 * Math.PI) / rays);
        ctx.fillStyle = "rgba(255, 255, 255, 0.015)";
        ctx.fill();
    }
    ctx.restore();
    sunburstAngle += 0.002;
}

function drawPlane() {
    ctx.save();
    ctx.translate(planePos.x, planePos.y);
    if (planeImg.complete) {
        ctx.drawImage(planeImg, -30, -20, 60, 45);
    } else {
        // ምስሉ ሎድ እስኪያደርግ ዲፎልት ቀይ ትሪያንግል
        ctx.fillStyle = "#e50b2c";
        ctx.beginPath();
        ctx.moveTo(30, 0);
        ctx.lineTo(-10, -15);
        ctx.lineTo(-20, 0);
        ctx.lineTo(-10, 15);
        ctx.closePath();
        ctx.fill();
    }
    ctx.restore();
}

function drawCurve() {
    ctx.beginPath();
    ctx.moveTo(0, canvas.height);
    ctx.quadraticCurveTo(planePos.x * 0.4, canvas.height * 0.9, planePos.x - 10, planePos.y + 10);
    ctx.lineWidth = 5;
    ctx.strokeStyle = "#e50b2c";
    ctx.stroke();

    ctx.lineTo(planePos.x, canvas.height);
    ctx.lineTo(0, canvas.height);
    let gradient = ctx.createLinearGradient(0, planePos.y, 0, canvas.height);
    gradient.addColorStop(0, "rgba(229, 11, 44, 0.5)");
    gradient.addColorStop(1, "rgba(229, 11, 44, 0.0)");
    ctx.fillStyle = gradient;
    ctx.fill();
}

// ================= GAME LOOP =================
let animationId;
function gameLoop() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawSunburst();

    if (gameState === 'WAITING') {
        multiplierDisplay.style.color = "#ffffff";
        multiplierDisplay.style.fontSize = "3rem";
        multiplierDisplay.innerText = "WAITING...";
        
        statusText.style.display = "block";
        statusText.innerText = `NEXT ROUND IN ${countdownTimer}s`;
        
        planePos = { x: 0, y: canvas.height }; 
    } 
    else if (gameState === 'FLYING') {
        statusText.style.display = "none";
        multiplierDisplay.style.fontSize = "4.5rem";
        multiplierDisplay.style.color = "#ffffff";
        
        multiplier += 0.002 * (1 + (multiplier * 0.1));
        multiplierDisplay.innerText = multiplier.toFixed(2) + "x";

        if (Math.random() < 0.1) playSound("fly");

        if (planePos.x < canvas.width * 0.75) planePos.x += 2.5;
        if (planePos.y > canvas.height * 0.2) planePos.y -= 1.5;
        let wobble = Math.sin(Date.now() / 200) * 2;
        planePos.y += wobble * 0.1;

        drawCurve();
        drawPlane();

        // Auto Cashout ሎጂክ
        [1, 2].forEach(id => {
            let bet = bets[id];
            if (bet.state === 'IN_GAME' && bet.isAuto) {
                let targetMult = parseFloat(document.getElementById(`autoCashoutInput${id}`).value);
                if (multiplier >= targetMult) {
                    executeCashout(id);
                }
            }
        });

        syncButtons();

        if (multiplier >= crashPoint) {
            triggerCrash();
        }
    } 
    else if (gameState === 'CRASHED') {
        statusText.style.display = "block";
        statusText.style.color = "#e50b2c";
        statusText.innerText = "FLEW AWAY!";
        multiplierDisplay.style.color = "#e50b2c";

        // አውሮፕላኑ ከስክሪኑ በፍጥነት እንዲወጣ (Flew Away ውጤት)
        planePos.x += 15;
        planePos.y -= 10;
        drawCurve();
        drawPlane();
    }

    animationId = requestAnimationFrame(gameLoop);
}

// ================= ROUND MANAGERS =================
function startCountdown() {
    gameState = 'WAITING';
    countdownTimer = 10;
    multiplier = 1.00;
    
    // ቀጣዩ ዙር ሲጀምር በሙሉ ፓነሎችን ሪሴት እናደርጋለን
    [1, 2].forEach(id => {
        if(bets[id].state === 'CASHED_OUT' || bets[id].state === 'CRASHED' || bets[id].state === 'IN_GAME') {
            bets[id].state = 'IDLE';
        }
    });
    syncButtons();

    let intervalId = setInterval(() => {
        countdownTimer--;
        
        if (countdownTimer === 1) {
            [1, 2].forEach(id => {
                if (bets[id].state === 'QUEUED') {
                    placeBetAPI(id); 
                }
            });
        }

        if (countdownTimer <= 0) {
            clearInterval(intervalId);
            startRound();
        }
    }, 1000);
}

function startRound() {
    gameState = 'FLYING';
    crashPoint = generateCrashPoint();
    
    [1, 2].forEach(id => {
        if(bets[id].state === 'WAITING') {
            bets[id].state = 'IN_GAME';
        }
    });
    syncButtons(); 
}

// ================= 3. TRIGGER CRASH (ውጤቱን በቋሚነት ወደ Redis የሚልክ) =================
function triggerCrash() {
    gameState = 'CRASHED';
    playSound("crash");
    
    let finalCrashPoint = parseFloat(multiplier.toFixed(2));

    // UI ታሪክ ማዘመን
    crashHistory.unshift(finalCrashPoint);
    if(crashHistory.length > 20) crashHistory.pop();
    renderHistory();

    // 🚀 ውጤቱን ወደ Python/Redis ቋሚ አድርጎ እንዲያስቀምጥ በ API መላክ
    fetch('/api/save_history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ multiplier: finalCrashPoint })
    }).catch(e => console.error("History save error:", e));

    // የተሸነፉ ፓነሎችን ወደ CRASHED መቀየር
    [1, 2].forEach(id => {
        if (bets[id].state === 'IN_GAME') {
            bets[id].state = 'CRASHED';
        }
    });
    syncButtons();

    setTimeout(() => {
        startCountdown();
    }, 3000);
}

// ጅማሬ
updateInputUI();
startCountdown();
requestAnimationFrame(gameLoop);
