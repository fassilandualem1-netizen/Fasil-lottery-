// ==========================================
// 🚀 Aviator Game Client-Side Logic
// ==========================================

const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const multiplierDisplay = document.getElementById("multiplierDisplay");
const statusText = document.getElementById("statusText");
const historyBar = document.getElementById("historyBar");
const balanceDisplay = document.getElementById('balanceDisplay');

const tg = window.Telegram ? window.Telegram.WebApp : null;
const userId = tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id.toString() : "8488592165";

const socket = io();

let gameState = 'WAITING'; 
let multiplier = 1.00;
let crashHistory = [1.28, 2.68, 1.44, 4.36, 2.02, 1.91]; 
let planePos = { x: 0, y: 500 };
let sunburstAngle = 0;

let bets = {
    1: { state: 'IDLE', amount: 20 }, 
    2: { state: 'IDLE', amount: 20 }
};

// ================= SOUND LOGIC =================
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
function playSound(type) {
    if(audioCtx.state === 'suspended') audioCtx.resume();
    try {
        let osc = audioCtx.createOscillator();
        let gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);

        if (type === "fly") {
            osc.frequency.setValueAtTime(80 + (multiplier * 5), audioCtx.currentTime);
            gain.gain.setValueAtTime(0.01, audioCtx.currentTime);
            osc.start(); osc.stop(audioCtx.currentTime + 0.1);
        } else if (type === "win") {
            osc.frequency.setValueAtTime(600, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(1500, audioCtx.currentTime + 0.3);
            gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
            osc.start(); osc.stop(audioCtx.currentTime + 0.4);
        } else if (type === "crash") {
            osc.type = "sawtooth";
            osc.frequency.setValueAtTime(150, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(40, audioCtx.currentTime + 0.5);
            gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
            osc.start(); osc.stop(audioCtx.currentTime + 0.5);
        }
    } catch (e) {}
}

// ================= SERVER EVENTS =================
socket.on('game_update', function(data) {
    let oldState = gameState;
    gameState = data.status;
    multiplier = data.multiplier;

    if (gameState === 'WAITING') {
        if (oldState !== 'WAITING') {
            planePos = { x: 0, y: canvas.height };
            resetBetsForNewRound();
        }
    } else if (gameState === 'FLYING') {
        if (oldState === 'WAITING') {
            [1, 2].forEach(id => { if(bets[id].state === 'WAITING') bets[id].state = 'IN_GAME'; });
        }
    } else if (gameState === 'CRASHED') {
        if (oldState !== 'CRASHED') handleCrashLocally();
    }
});

// ================= UI & ACTIONS =================
function updateInputUI() {
    [1, 2].forEach(id => {
        document.getElementById(`betInput${id}`).value = bets[id].amount;
        if(bets[id].state === 'IDLE') document.getElementById(`btnSub${id}`).innerText = `${bets[id].amount.toFixed(2)} ETB`;
    });
}

function adjustBet(panelId, delta) {
    if (bets[panelId].state !== 'IDLE') return;
    let newVal = bets[panelId].amount + delta;
    if (newVal >= 2) {
        bets[panelId].amount = newVal;
        updateInputUI();
    }
}

function setBet(panelId, amount) {
    if (bets[panelId].state !== 'IDLE') return;
    bets[panelId].amount = amount;
    updateInputUI();
}

async function handleAction(panelId) {
    let bet = bets[panelId];
    const btn = document.getElementById(`btnAction${panelId}`);

    if (bet.state === 'IDLE') {
        const response = await fetch('/api/dino/bet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, bet_amount: bet.amount })
        });
        const result = await response.json();
        if (result.status === "success") {
            if (balanceDisplay) balanceDisplay.innerText = result.new_balance.toFixed(2);
            bet.state = 'WAITING';
            btn.className = "action-btn btn-cancel";
            btn.innerHTML = `WAITING <div class="btn-subtext">Next round</div>`;
        } else alert(result.message || "ስህተት ተፈጥሯል");
    } else if (bet.state === 'IN_GAME' && gameState === 'FLYING') {
        bet.state = 'CASHED_OUT';
        btn.className = "action-btn btn-disabled";
        btn.innerHTML = `CASHED OUT <div class="btn-subtext">${(bet.amount * multiplier).toFixed(2)} ETB</div>`;
        playSound("win");
        fetch('/api/dino/cashout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, bet_amount: bet.amount, multiplier: multiplier })
        });
    }
}

function syncButtons() {
    [1, 2].forEach(id => {
        let bet = bets[id];
        let btn = document.getElementById(`btnAction${id}`);
        if (bet.state === 'IN_GAME') {
            btn.className = "action-btn btn-cashout";
            btn.innerHTML = `CASH OUT <div class="btn-subtext">${(bet.amount * multiplier).toFixed(2)} ETB</div>`;
        }
    });
}

function handleCrashLocally() {
    playSound("crash");
    crashHistory.unshift(multiplier);
    if(crashHistory.length > 20) crashHistory.pop();
    renderHistory();
    [1, 2].forEach(id => {
        if (bets[id].state === 'IN_GAME') {
            bets[id].state = 'IDLE';
            document.getElementById(`btnAction${id}`).className = "action-btn btn-disabled";
            document.getElementById(`btnAction${id}`).innerHTML = `CRASHED <div class="btn-subtext">0.00 ETB</div>`;
        }
    });
}

function renderHistory() {
    historyBar.innerHTML = crashHistory.map(m => `<div class="history-chip ${m < 2 ? 'color-blue' : 'color-pink'}">${m.toFixed(2)}x</div>`).join('');
}

// ================= ANIMATION LOOP =================
function renderLoop() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (gameState === 'FLYING') {
        if (planePos.x < canvas.width * 0.7) planePos.x += 2.5;
        if (planePos.y > canvas.height * 0.3) planePos.y -= 1.5;
        multiplierDisplay.innerText = multiplier.toFixed(2) + "x";
        syncButtons();
    }
    requestAnimationFrame(renderLoop);
}

updateInputUI();
renderLoop();
renderHistory();
