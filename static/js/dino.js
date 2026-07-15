// ==========================================
// 🚀 Aviator Game Client-Side Logic (dino.js)
// ==========================================

const canvas = document.getElementById("gameCanvas");
const ctx = canvas ? canvas.getContext("2d") : null;
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
            if (canvas) planePos = { x: 0, y: canvas.height };
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
function resetBetsForNewRound() {
    [1, 2].forEach(id => {
        let bet = bets[id];
        let btn = document.getElementById(`btnAction${id}`);
        
        // ውርርድ ካላደረጉ ወደ ነበረበት (IDLE) ይመለሳል
        if (bet.state !== 'WAITING') {
            bet.state = 'IDLE';
            if (btn) {
                btn.className = "action-btn btn-bet";
                btn.innerHTML = `<div class="btn-title">BET</div><div class="btn-subtext" id="btnSub${id}">${bet.amount.toFixed(2)} ETB</div>`;
            }
        }
    });
}

function updateInputUI() {
    [1, 2].forEach(id => {
        let input = document.getElementById(`betInput${id}`);
        if (input) input.value = bets[id].amount.toFixed(2);
        
        if (bets[id].state === 'IDLE') {
            let subText = document.getElementById(`btnSub${id}`);
            if (subText) subText.innerText = `${bets[id].amount.toFixed(2)} ETB`;
        }
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
    if (!btn) return;

    if (bet.state === 'IDLE') {
        // ውርርድ (Bet) ማድረግ
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
            btn.innerHTML = `<div class="btn-title">WAITING</div><div class="btn-subtext">Next round</div>`;
        } else {
            alert(result.message || "ስህተት ተፈጥሯል");
        }
    } 
    else if (bet.state === 'IN_GAME' && gameState === 'FLYING') {
        // ገንዘብ ማውጣት (Cashout)
        bet.state = 'CASHED_OUT';
        let winAmount = (bet.amount * multiplier).toFixed(2);
        
        btn.className = "action-btn btn-disabled";
        btn.innerHTML = `<div class="btn-title">CASHED OUT</div><div class="btn-subtext">${winAmount} ETB</div>`;
        playSound("win");
        
        const response = await fetch('/api/dino/cashout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, bet_amount: bet.amount, multiplier: multiplier })
        });
        const result = await response.json();
        
        if (result.status === "success" && balanceDisplay) {
            balanceDisplay.innerText = result.new_balance.toFixed(2);
        }
    }
}

function syncButtons() {
    [1, 2].forEach(id => {
        let bet = bets[id];
        let btn = document.getElementById(`btnAction${id}`);
        if (bet.state === 'IN_GAME' && btn) {
            btn.className = "action-btn btn-cashout";
            btn.innerHTML = `<div class="btn-title">CASH OUT</div><div class="btn-subtext">${(bet.amount * multiplier).toFixed(2)} ETB</div>`;
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
            let btn = document.getElementById(`btnAction${id}`);
            if (btn) {
                btn.className = "action-btn btn-disabled";
                btn.innerHTML = `<div class="btn-title">CRASHED</div><div class="btn-subtext">0.00 ETB</div>`;
            }
        }
    });
}

function renderHistory() {
    if (!historyBar) return;
    historyBar.innerHTML = crashHistory.map(m => {
        let colorClass = m < 2 ? 'color-blue' : (m < 10 ? 'color-purple' : 'color-pink');
        return `<span class="history-item ${colorClass}">${m.toFixed(2)}x</span>`;
    }).join('');
}

// ================= ANIMATION LOOP =================
function renderLoop() {
    if (!ctx || !canvas) return requestAnimationFrame(renderLoop);
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    if (gameState === 'FLYING' || gameState === 'CRASHED') {
        if (gameState === 'FLYING') {
            if (planePos.x < canvas.width * 0.7) planePos.x += 2.5;
            if (planePos.y > canvas.height * 0.3) planePos.y -= 1.5;
            
            if (multiplierDisplay) {
                multiplierDisplay.innerText = multiplier.toFixed(2) + "x";
                multiplierDisplay.style.color = "#ffffff";
            }
            if (statusText) statusText.style.display = "none";
            syncButtons();
        }

        // የ አውሮፕላን መንገድ (Graph curve)
        ctx.beginPath();
        ctx.moveTo(0, canvas.height);
        ctx.quadraticCurveTo(planePos.x * 0.5, canvas.height, planePos.x, planePos.y);
        ctx.lineTo(planePos.x, canvas.height);
        ctx.fillStyle = "rgba(229, 11, 44, 0.2)"; 
        ctx.fill();
        
        // የ አውሮፕላን ቀይ መስመር
        ctx.beginPath();
        ctx.moveTo(0, canvas.height);
        ctx.quadraticCurveTo(planePos.x * 0.5, canvas.height, planePos.x, planePos.y);
        ctx.strokeStyle = "#e50b2c";
        ctx.lineWidth = 4;
        ctx.stroke();

        // ጊዜያዊ የ አውሮፕላን ምስል (ነጭ ክብ) - በኋላ በምስል መቀየር ትችላለህ
        ctx.beginPath();
        ctx.arc(planePos.x, planePos.y, 8, 0, Math.PI * 2);
        ctx.fillStyle = "#ffffff";
        ctx.fill();
        
        if (gameState === 'CRASHED') {
            if (multiplierDisplay) multiplierDisplay.style.color = "#e50b2c";
            if (statusText) {
                statusText.innerText = "FLEW AWAY!";
                statusText.style.display = "block";
            }
        }
    } else if (gameState === 'WAITING') {
        if (multiplierDisplay) {
            multiplierDisplay.innerText = "1.00x";
            multiplierDisplay.style.color = "#ffffff";
        }
        if (statusText) {
            statusText.innerText = "WAITING FOR NEXT ROUND";
            statusText.style.display = "block";
        }
    }
    
    requestAnimationFrame(renderLoop);
}

// ጀምር
updateInputUI();
renderLoop();
renderHistory();
