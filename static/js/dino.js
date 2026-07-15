const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const multiplierDisplay = document.getElementById("multiplierDisplay");
const betAmountInput = document.getElementById("betAmount");
const autoCashoutInput = document.getElementById("autoCashout");
const autoCashoutToggle = document.getElementById("autoCashoutToggle");
const btnAction = document.getElementById("btnAction");
const stepperBtns = document.querySelectorAll('.stepper-btn');
const historyBar = document.getElementById("historyBar");
const balanceDisplay = document.getElementById('balanceDisplay');

const tg = window.Telegram ? window.Telegram.WebApp : null;
const userId = tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id.toString() : "8488592165";

// 🎮 የጨዋታ State Management
let gameState = 'WAITING'; // WAITING, FLYING, CRASHED
let userState = 'IDLE';    // IDLE, BET_PLACED, IN_GAME, CASHED_OUT
let multiplier = 1.00;
let crashPoint = 1.00;
let gameFrame = 0;
let countdownTimer = 10;
let crashHistory = [];

// Auto Cashout Toggle Logic
autoCashoutToggle.addEventListener('change', (e) => {
    autoCashoutInput.disabled = !e.target.checked;
});

function generateCrashPoint() {
    let rand = Math.random();
    if (rand < 0.10) return 1.00 + Math.random() * 0.05;
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
            osc.type = "sawtooth";
            osc.frequency.setValueAtTime(100 + (multiplier * 20), audioCtx.currentTime);
            gain.gain.setValueAtTime(0.02, audioCtx.currentTime);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.1);
        } else if (type === "win") {
            osc.type = "sine";
            osc.frequency.setValueAtTime(500, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(1200, audioCtx.currentTime + 0.3);
            gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.4);
        } else if (type === "crash") {
            osc.type = "triangle";
            osc.frequency.setValueAtTime(180, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(40, audioCtx.currentTime + 0.5);
            gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.5);
        }
    } catch (e) {}
}

// ✈️ አውሮፕላን (Triangle Shape)
const plane = {
    x: 50,
    y: 450,
    size: 25,
    draw() {
        ctx.save();
        ctx.translate(this.x, this.y);
        ctx.rotate(-Math.PI / 8);

        // የአውሮፕላን አካል
        ctx.fillStyle = "#00d2d3";
        ctx.beginPath();
        ctx.moveTo(this.size, 0); // አፍንጫ
        ctx.lineTo(-this.size, this.size / 1.5); // የታችኛው ክንፍ
        ctx.lineTo(-this.size / 2, 0); // ጀርባ
        ctx.lineTo(-this.size, -this.size / 1.5); // የላይኛው ክንፍ
        ctx.closePath();
        ctx.fill();

        // የሞተር እሳት
        if (gameState === 'FLYING' && gameFrame % 4 < 2) {
            ctx.fillStyle = "#ff9f43";
            ctx.beginPath();
            ctx.moveTo(-this.size / 2 - 2, 0);
            ctx.lineTo(-this.size - 15, 10);
            ctx.lineTo(-this.size - 8, 0);
            ctx.lineTo(-this.size - 15, -10);
            ctx.closePath();
            ctx.fill();
        }
        ctx.restore();
    }
};

// ☁️ ደመናዎች (Clouds)
let clouds = [];
function drawClouds() {
    if (gameState === 'FLYING' && Math.random() < 0.05) {
        clouds.push({ x: canvas.width, y: Math.random() * 300, size: 20 + Math.random() * 30 });
    }
    ctx.fillStyle = "rgba(255, 255, 255, 0.6)";
    for (let i = clouds.length - 1; i >= 0; i--) {
        clouds[i].x -= 2 + (multiplier * 0.5); // በፍጥነት ይጓዛል
        
        let c = clouds[i];
        ctx.beginPath();
        ctx.arc(c.x, c.y, c.size, 0, Math.PI * 2);
        ctx.arc(c.x + c.size * 0.8, c.y - c.size * 0.2, c.size * 0.8, 0, Math.PI * 2);
        ctx.arc(c.x + c.size * 1.5, c.y, c.size * 0.9, 0, Math.PI * 2);
        ctx.fill();

        if (clouds[i].x + c.size * 2 < 0) clouds.splice(i, 1);
    }
}

// የበረራ መስመር
let flightPath = [];
function drawPath() {
    if (flightPath.length > 1) {
        ctx.strokeStyle = "rgba(0, 210, 211, 0.6)";
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(flightPath[0].x, flightPath[0].y);
        for (let i = 1; i < flightPath.length; i++) {
            ctx.lineTo(flightPath[i].x, flightPath[i].y);
        }
        ctx.stroke();
    }
}

function toggleStepper(disabled) {
    stepperBtns.forEach(btn => btn.disabled = disabled);
    betAmountInput.disabled = disabled;
    autoCashoutInput.disabled = disabled;
    autoCashoutToggle.disabled = disabled;
}

// ⏳ History ማደሻ
function updateHistory(crashedAt) {
    crashHistory.unshift(crashedAt);
    if (crashHistory.length > 6) crashHistory.pop();
    if (historyBar) {
        historyBar.innerHTML = crashHistory.map(m => 
            `<span style="padding: 5px 10px; border-radius: 5px; color: white; background: ${m >= 2.0 ? '#10ac84' : '#ee5253'}">${m.toFixed(2)}x</span>`
        ).join('');
    }
}

// 🎮 ዋናው Game Loop (ያለማቋረጥ የሚሰራ)
function gameLoop() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    gameFrame++;

    drawClouds();
    drawPath();

    if (gameState === 'WAITING') {
        ctx.fillStyle = "white";
        ctx.font = "bold 24px 'Segoe UI'";
        ctx.textAlign = "center";
        ctx.fillText(`Next round in ${countdownTimer}s...`, canvas.width / 2, canvas.height / 2);
        plane.draw();
    } 
    else if (gameState === 'FLYING') {
        multiplier += 0.002 * (1 + (multiplier * 0.1));
        multiplierDisplay.innerText = multiplier.toFixed(2) + "x";

        if (gameFrame % 10 === 0) playSound("fly");

        plane.x = 50 + (multiplier - 1) * 100;
        plane.y = 450 - (multiplier - 1) * 70;
        if (plane.x > canvas.width - 50) plane.x = canvas.width - 50;
        if (plane.y < 50) plane.y = 50;

        flightPath.push({ x: plane.x, y: plane.y });

        // Auto Cashout Check
        if (userState === 'IN_GAME' && autoCashoutToggle.checked) {
            const autoLimit = parseFloat(autoCashoutInput.value);
            if (!isNaN(autoLimit) && autoLimit > 1.0 && multiplier >= autoLimit) {
                cashOutUser();
            }
        }

        // Crash Check
        if (multiplier >= crashPoint) {
            triggerCrash();
        } else {
            plane.draw();
            if (userState === 'IN_GAME') {
                btnAction.innerText = `CASH OUT (ETB ${(betAmountInput.value * multiplier).toFixed(2)})`;
            }
        }
    } 
    else if (gameState === 'CRASHED') {
        multiplierDisplay.innerText = "CRASHED!💥";
        ctx.fillStyle = "#ee5253";
        ctx.font = "bold 30px 'Segoe UI'";
        ctx.textAlign = "center";
        ctx.fillText(`FLEW AWAY @ ${multiplier.toFixed(2)}x`, canvas.width / 2, canvas.height / 2);
    }

    requestAnimationFrame(gameLoop);
}

// ውርርድ ማስገባት (በመጠበቂያ ሰዓት)
async function placeBet() {
    const betAmount = parseFloat(betAmountInput.value);
    if (isNaN(betAmount) || betAmount <= 0) return;

    btnAction.disabled = true;
    toggleStepper(true);

    try {
        const response = await fetch('/api/dino/bet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, bet_amount: betAmount })
        });
        const result = await response.json();

        if (result.status === "success") {
            userState = 'BET_PLACED';
            if (balanceDisplay) balanceDisplay.innerText = result.new_balance.toFixed(2);
            btnAction.innerText = "ውርርድ ገብቷል (WAITING...)";
            btnAction.className = "action-btn waiting-mode";
        } else {
            alert(result.message || "በቂ ሂሳብ የሎትም!");
            btnAction.disabled = false;
            toggleStepper(false);
        }
    } catch (e) {
        btnAction.disabled = false;
        toggleStepper(false);
    }
}

// ተጫዋቹ ራሱ Cashout ሲያደርግ (ጨዋታው አይቋረጥም)
async function cashOutUser() {
    if (userState !== 'IN_GAME') return;
    userState = 'CASHED_OUT';
    btnAction.disabled = true;
    playSound("win");

    const betAmount = parseFloat(betAmountInput.value);
    try {
        const response = await fetch('/api/dino/cashout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, bet_amount: betAmount, multiplier: multiplier })
        });
        const result = await response.json();

        if (result.status === "success") {
            if (balanceDisplay) balanceDisplay.innerText = result.new_balance.toFixed(2);
            btnAction.innerText = `አሸንፈዋል! (+${result.win_amount})`;
            btnAction.className = "action-btn win-mode";
        }
    } catch (e) { console.error(e); }
}

// ክራሽ ሲያደርግ
function triggerCrash() {
    gameState = 'CRASHED';
    playSound("crash");
    updateHistory(multiplier);

    if (userState === 'IN_GAME') {
        userState = 'IDLE'; // ተጫዋቹ ተሸንፏል
        btnAction.innerText = "ተሸንፈዋል!";
        btnAction.disabled = true;
    }

    // ከ 2 ሰከንድ በኋላ አዲሱን ዙር ቆጠራ ይጀምራል
    setTimeout(() => {
        startCountdown();
    }, 2000);
}

// 10 ሰከንድ ቆጠራ
let intervalId;
function startCountdown() {
    gameState = 'WAITING';
    countdownTimer = 10;
    multiplier = 1.00;
    multiplierDisplay.innerText = "1.00x";
    flightPath = [];
    clouds = [];
    plane.x = 50;
    plane.y = 450;
    
    if (userState !== 'BET_PLACED') {
        userState = 'IDLE';
        btnAction.disabled = false;
        btnAction.innerText = "ውርርድ ፍጠር (BET)";
        btnAction.className = "action-btn bet-mode";
        toggleStepper(false);
    }

    clearInterval(intervalId);
    intervalId = setInterval(() => {
        countdownTimer--;
        if (countdownTimer <= 0) {
            clearInterval(intervalId);
            startRound();
        }
    }, 1000);
}

// አዲስ ዙር ሲጀምር
function startRound() {
    gameState = 'FLYING';
    crashPoint = generateCrashPoint();
    gameFrame = 0;

    if (userState === 'BET_PLACED') {
        userState = 'IN_GAME';
        btnAction.disabled = false;
        btnAction.className = "action-btn cashout-mode";
    } else {
        // ተጫዋቹ ካልተወራረደ መመልከት (Spectate) ብቻ ይሆናል
        userState = 'IDLE';
        btnAction.disabled = true;
        btnAction.innerText = "ጨዋታ ላይ ነው...";
        toggleStepper(true);
    }
}

// Button Click Logic
btnAction.addEventListener("click", function() {
    if (gameState === 'WAITING' && userState === 'IDLE') {
        placeBet(); // ቆጠራ ላይ እያለ ውርርድ ያስገባል
    } else if (gameState === 'FLYING' && userState === 'IN_GAME') {
        cashOutUser(); // አውሮፕላኑ እየበረረ Cashout ያደርጋል
    }
});

// ጨዋታውን ለመጀመሪያ ጊዜ ሲከፈት ጀምረው
startCountdown();
requestAnimationFrame(gameLoop);
