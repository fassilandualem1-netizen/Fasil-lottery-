const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const multiplierDisplay = document.getElementById("multiplierDisplay");
const statusText = document.getElementById("statusText");
const historyBar = document.getElementById("historyBar");
const balanceDisplay = document.getElementById('balanceDisplay');

const tg = window.Telegram ? window.Telegram.WebApp : null;
const userId = tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id.toString() : "8488592165";

// ==========================================
// 🔌 SOCKET.IO (ከ Python ሰርቨር ጋር መገናኛ)
// ==========================================
// ማሳሰቢያ፡ HTML ፋይልህ ላይ የ socket.io script መግባቱን አረጋግጥ
const socket = io();

// 🎮 የጨዋታ State Management (አሁን ከሰርቨር ነው የሚመጣው)
let gameState = 'WAITING'; 
let multiplier = 1.00;
let crashHistory = [1.28, 2.68, 1.44, 4.36, 2.02, 1.91]; 

// 💸 የውርርድ (Dual Bet) State
let bets = {
    1: { state: 'IDLE', amount: 20 }, 
    2: { state: 'IDLE', amount: 20 }
};

// ==========================================
// 📡 SERVER EVENTS (ሰርቨሩ ሲያዘን የምናደርገው)
// ==========================================
socket.on('game_update', function(data) {
    let oldState = gameState;
    gameState = data.status;
    multiplier = data.multiplier;

    // 1. ጨዋታው ሊጀምር ሲል (WAITING)
    if (gameState === 'WAITING') {
        if (oldState !== 'WAITING') {
            planePos = { x: 0, y: canvas.height }; // አውሮፕላኑን ወደ መሬት መመለስ
            resetBetsForNewRound();
        }
    } 
    // 2. አውሮፕላኑ ሲነሳ (FLYING)
    else if (gameState === 'FLYING') {
        if (oldState === 'WAITING') {
            // ውርርድ ያደረጉትን ወደ IN_GAME መቀየር
            [1, 2].forEach(id => {
                if(bets[id].state === 'WAITING') bets[id].state = 'IN_GAME';
            });
        }
    } 
    // 3. አውሮፕላኑ ሲፈነዳ (CRASHED)
    else if (gameState === 'CRASHED') {
        if (oldState !== 'CRASHED') {
            handleCrashLocally();
        }
    }
});

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

// ================= UI & INPUT LOGIC =================
function updateInputUI() {
    document.getElementById("betInput1").value = bets[1].amount;
    document.getElementById("betInput2").value = bets[2].amount;
    
    if(bets[1].state === 'IDLE') document.getElementById("btnSub1").innerText = `${bets[1].amount.toFixed(2)} ETB`;
    if(bets[2].state === 'IDLE') document.getElementById("btnSub2").innerText = `${bets[2].amount.toFixed(2)} ETB`;
}

function adjustBet(panelId, amount) {
    if (bets[panelId].state !== 'IDLE') return;
    let newVal = bets[panelId].amount + amount;
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

// ================= HISTORY LOGIC =================
function renderHistory() {
    historyBar.innerHTML = crashHistory.map(m => {
        let colorClass = m < 2.0 ? 'color-blue' : (m < 10.0 ? 'color-purple' : 'color-pink');
        return `<div class="history-chip ${colorClass}">${m.toFixed(2)}x</div>`;
    }).join('');
    historyBar.scrollLeft = 0;
}
renderHistory(); 

// ================= BUTTON ACTION LOGIC =================
async function handleAction(panelId) {
    let bet = bets[panelId];
    const btn = document.getElementById(`btnAction${panelId}`);

    // 1. ውርርድ ማስገባት
    if (bet.state === 'IDLE') {
        try {
            const response = await fetch('/api/dino/bet', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, bet_amount: bet.amount })
            });
            const result = await response.json();
            
            if (result.status === "success") {
                if (balanceDisplay) balanceDisplay.innerText = result.new_balance.toFixed(2);
                
                // ጨዋታው እየበረረ ከሆነ ለቀጣዩ ዙር ይጠብቃል፣ ካልሆነ አሁኑኑ ይገባል
                bet.state = (gameState === 'FLYING') ? 'WAITING' : 'WAITING';
                btn.className = "action-btn btn-cancel";
                btn.innerHTML = `CANCEL <div class="btn-subtext">Waiting for next round</div>`;
            } else {
                alert(result.message || "በቂ ሂሳብ የሎትም!");
            }
        } catch (e) { console.error("Bet Error: ", e); }
    } 
    // 2. ውርርድ መሰረዝ (ከመጀመሩ በፊት)
    else if (bet.state === 'WAITING' && gameState === 'WAITING') {
        bet.state = 'IDLE';
        btn.className = "action-btn btn-bet";
        btn.innerHTML = `BET <div class="btn-subtext">${bet.amount.toFixed(2)} ETB</div>`;
        // ማሳሰቢያ፡ ገንዘቡ እንዲመለስ ከፈለግህ cancel API backend ላይ መጨመር አለብህ
    }
    // 3. Cash Out ማድረግ
    else if (bet.state === 'IN_GAME' && gameState === 'FLYING') {
        bet.state = 'CASHED_OUT';
        btn.className = "action-btn btn-disabled";
        let winAmount = (bet.amount * multiplier).toFixed(2);
        btn.innerHTML = `CASHED OUT <div class="btn-subtext">${winAmount} ETB</div>`;
        playSound("win");

        try {
            const response = await fetch('/api/dino/cashout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, bet_amount: bet.amount, multiplier: multiplier })
            });
            const result = await response.json();
            if (result.status === "success") {
                if (balanceDisplay) balanceDisplay.innerText = result.new_balance.toFixed(2);
            }
        } catch (e) { console.error("Cashout Error: ", e); }
    }
}

function syncButtons() {
    [1, 2].forEach(id => {
        let bet = bets[id];
        let btn = document.getElementById(`btnAction${id}`);

        if (bet.state === 'IDLE') {
            btn.className = "action-btn btn-bet";
            btn.innerHTML = `BET <div class="btn-subtext">${bet.amount.toFixed(2)} ETB</div>`;
            document.getElementById(`betInput${id}`).disabled = false;
        } else if (bet.state === 'IN_GAME') {
            btn.className = "action-btn btn-cashout";
            let winAmount = (bet.amount * multiplier).toFixed(2);
            btn.innerHTML = `CASH OUT <div class="btn-subtext">${winAmount} ETB</div>`;
            document.getElementById(`betInput${id}`).disabled = true;
        }
    });
}

// ================= GAME LOGIC HELPERS =================
function resetBetsForNewRound() {
    [1, 2].forEach(id => {
        if(bets[id].state === 'CASHED_OUT' || bets[id].state === 'IN_GAME') {
            bets[id].state = 'IDLE';
        }
    });
    syncButtons();
}

function handleCrashLocally() {
    playSound("crash");
    
    // ታሪክ ውስጥ መጨመር
    crashHistory.unshift(multiplier);
    if(crashHistory.length > 20) crashHistory.pop();
    renderHistory();

    // Cash out ያላደረጉትን ማስሸነፍ
    [1, 2].forEach(id => {
        if (bets[id].state === 'IN_GAME') {
            bets[id].state = 'IDLE';
            let btn = document.getElementById(`btnAction${id}`);
            btn.className = "action-btn btn-disabled";
            btn.innerHTML = `CRASHED <div class="btn-subtext">0.00 ETB</div>`;
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
        ctx.fillStyle = "rgba(255, 255, 255, 0.02)";
        ctx.fill();
    }
    ctx.restore();
    sunburstAngle += 0.002;
}

function drawPlane() {
    ctx.save();
    ctx.translate(planePos.x, planePos.y);
    ctx.fillStyle = "#e50b2c";
    ctx.beginPath();
    ctx.moveTo(30, 0);
    ctx.lineTo(-10, -15);
    ctx.lineTo(-20, 0);
    ctx.lineTo(-10, 15);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
}

function drawCurve() {
    ctx.beginPath();
    ctx.moveTo(0, canvas.height);
    ctx.quadraticCurveTo(planePos.x * 0.5, canvas.height, planePos.x, planePos.y);
    ctx.lineWidth = 6;
    ctx.strokeStyle = "#e50b2c";
    ctx.stroke();

    ctx.lineTo(planePos.x, canvas.height);
    ctx.lineTo(0, canvas.height);
    let gradient = ctx.createLinearGradient(0, planePos.y, 0, canvas.height);
    gradient.addColorStop(0, "rgba(229, 11, 44, 0.4)");
    gradient.addColorStop(1, "rgba(229, 11, 44, 0.0)");
    ctx.fillStyle = gradient;
    ctx.fill();
}

// በ 60FPS የሚሽከረከረው የግራፊክስ ሞተር
function renderLoop() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawSunburst();

    if (gameState === 'WAITING') {
        multiplierDisplay.style.color = "#ffffff";
        multiplierDisplay.style.fontSize = "3rem";
        multiplierDisplay.innerText = "WAITING FOR NEXT ROUND...";
        
        statusText.style.display = "none";
    } 
    else if (gameState === 'FLYING') {
        statusText.style.display = "none";
        multiplierDisplay.style.fontSize = "4.5rem";
        multiplierDisplay.style.color = "#ffffff";
        multiplierDisplay.innerText = multiplier.toFixed(2) + "x";

        if (Math.random() < 0.1) playSound("fly");

        // አውሮፕላኑን ማንቀሳቀስ
        if (planePos.x < canvas.width * 0.7) planePos.x += 2.5;
        if (planePos.y > canvas.height * 0.3) planePos.y -= 1.5;

        let wobble = Math.sin(Date.now() / 200) * 3;
        planePos.y += wobble * 0.1;

        drawCurve();
        drawPlane();
        syncButtons(); // ቁልፎች ላይ ያለውን Win Amount ቆጠራ ለማሳየት
    } 
    else if (gameState === 'CRASHED') {
        statusText.style.display = "block";
        statusText.style.color = "#e50b2c";
        statusText.innerText = "FLEW AWAY!";
        multiplierDisplay.style.color = "#e50b2c";
        multiplierDisplay.innerText = multiplier.toFixed(2) + "x";
    }

    requestAnimationFrame(renderLoop);
}

// ጅማሬ
updateInputUI();
requestAnimationFrame(renderLoop);
