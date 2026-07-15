const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const multiplierDisplay = document.getElementById("multiplierDisplay");
const betAmountInput = document.getElementById("betAmount");
const autoCashoutInput = document.getElementById("autoCashout");
const btnAction = document.getElementById("btnAction");
const stepperBtns = document.querySelectorAll('.stepper-btn');

const tg = window.Telegram ? window.Telegram.WebApp : null;
const userId = tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id.toString() : "8488592165";

let isPlaying = false;
let isGameOver = false;
let multiplier = 1.00;
let animationFrameId;
let gameFrame = 0;

// 🛡️ የHouse Edge እና የክራሽ አልጎሪዝም
let crashPoint = 1.00; 

function generateCrashPoint() {
    let rand = Math.random();
    // 10% የመሸነፍ ዕድል (Instant crash ከ 1.00 - 1.05) -> አንተን ከትልቅ ኪሳራ ለመጠበቅ
    if (rand < 0.10) {
        return 1.00 + Math.random() * 0.05;
    }
    // ቀሪው 90% ፍትሃዊ በሆነ መልኩ በኤክስፖኔንሻል ከርቭ ይጨምራል
    return 1.05 + (0.95 / (Math.random() + 0.01));
}

// 🔊 የድምፅ ማጫወቻ (Web Audio API - ያለምንም ኤክስትራ ፋይል በኮድ ብቻ ድምፅ የሚፈጥር)
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

function playSound(type) {
    try {
        let osc = audioCtx.createOscillator();
        let gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);

        if (type === "fly") { // የሮኬት ድምፅ
            osc.type = "sawtooth";
            osc.frequency.setValueAtTime(100 + (multiplier * 20), audioCtx.currentTime);
            gain.gain.setValueAtTime(0.02, audioCtx.currentTime);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.1);
        } else if (type === "win") { // የድል ድምፅ
            osc.type = "sine";
            osc.frequency.setValueAtTime(500, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(1200, audioCtx.currentTime + 0.3);
            gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.4);
        } else if (type === "crash") { // የፍንዳታ ድምፅ
            osc.type = "triangle";
            osc.frequency.setValueAtTime(180, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(40, audioCtx.currentTime + 0.5);
            gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.5);
        }
    } catch (e) {
        console.log("Audio play blocked by browser settings.");
    }
}

// 🚀 የሮኬቱ መገኛና አቅጣጫዎች
const rocket = {
    x: 50,
    y: 450,
    size: 35,
    draw() {
        ctx.save();
        ctx.translate(this.x, this.y);
        ctx.rotate(-Math.PI / 6); // ወደ ላይ እንዲያይ ማድረግ

        // የሮኬት አካል
        ctx.fillStyle = "#e94560";
        ctx.beginPath();
        ctx.moveTo(0, -this.size);
        ctx.lineTo(this.size / 2, this.size);
        ctx.lineTo(-this.size / 2, this.size);
        ctx.closePath();
        ctx.fill();

        // ሮኬት ጭራ እሳት
        if (isPlaying && gameFrame % 4 < 2) {
            ctx.fillStyle = "#ff9f43";
            ctx.beginPath();
            ctx.moveTo(-10, this.size);
            ctx.lineTo(0, this.size + 15);
            ctx.lineTo(10, this.size);
            ctx.closePath();
            ctx.fill();
        }
        ctx.restore();
    }
};

// ኮከቦች (Stars)
let stars = [];
function drawStars() {
    if (Math.random() < 0.1) {
        stars.push({ x: canvas.width, y: Math.random() * 400, size: 1 + Math.random() * 2 });
    }
    ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
    for (let i = stars.length - 1; i >= 0; i--) {
        stars[i].x -= 4;
        ctx.fillRect(stars[i].x, stars[i].y, stars[i].size, stars[i].size);
        if (stars[i].x < 0) stars.splice(i, 1);
    }
}

// የበረራ መስመር (Neon Curve)
let flightPath = [];

function drawPath() {
    if (flightPath.length > 1) {
        ctx.strokeStyle = "rgba(0, 255, 204, 0.6)";
        ctx.lineWidth = 4;
        ctx.shadowColor = "#00ffcc";
        ctx.shadowBlur = 10;
        ctx.beginPath();
        ctx.moveTo(flightPath[0].x, flightPath[0].y);
        for (let i = 1; i < flightPath.length; i++) {
            ctx.lineTo(flightPath[i].x, flightPath[i].y);
        }
        ctx.stroke();
        ctx.shadowBlur = 0; // shadowን ማጥፋት ለሌሎች
    }
}

function toggleStepper(disabled) {
    stepperBtns.forEach(btn => btn.disabled = disabled);
    betAmountInput.disabled = disabled;
    autoCashoutInput.disabled = disabled;
}

// 🎮 የጨዋታው Loop
function gameLoop() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    gameFrame++;

    drawStars();
    drawPath();

    if (isPlaying) {
        // Multiplier ማሳደጊያ (በኤክስፖኔንሻል ፍጥነት ይጨምራል)
        multiplier += 0.002 * (1 + (multiplier * 0.1));
        multiplierDisplay.innerText = multiplier.toFixed(2) + "x";

        // ድምፅ ማጫወት በየጊዜው
        if (gameFrame % 10 === 0) playSound("fly");

        // ሮኬቱ ወደ ላይ የሚበርበት አኒሜሽን
        rocket.x = 50 + (multiplier - 1) * 120;
        rocket.y = 450 - (multiplier - 1) * 80;

        if (rocket.x > canvas.width - 50) rocket.x = canvas.width - 50;
        if (rocket.y < 50) rocket.y = 50;

        flightPath.push({ x: rocket.x, y: rocket.y });

        // Auto Cashout ቼክ ማድረጊያ
        const autoLimit = parseFloat(autoCashoutInput.value);
        if (!isNaN(autoLimit) && autoLimit > 1.0 && multiplier >= autoLimit) {
            endGame(true);
            return;
        }

        // CRASH መሆኑን ቼክ ማድረጊያ
        if (multiplier >= crashPoint) {
            endGame(false);
            return;
        }

        rocket.draw();
        btnAction.innerText = `CASH OUT (ETB ${(betAmountInput.value * multiplier).toFixed(2)})`;
    }

    animationFrameId = requestAnimationFrame(gameLoop);
}

// ጨዋታ ለመጀመር
async function startGame() {
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
            isPlaying = true;
            isGameOver = false;
            multiplier = 1.00;
            crashPoint = generateCrashPoint(); // አዲስ ክራሽ ፖይንት መፍጠር
            flightPath = [];
            stars = [];
            rocket.x = 50;
            rocket.y = 450;
            gameFrame = 0;

            // ቁልፉን ወደ Cashout ማዘጋጀት
            btnAction.disabled = false;
            btnAction.className = "action-btn cashout-mode";
            btnAction.style.display = "block";

            // ባላንስ ማደስ
            const balanceEl = document.getElementById('balanceDisplay') || document.getElementById('balance');
            if (balanceEl) balanceEl.innerText = result.new_balance.toFixed(2) + " ETB";

            gameLoop();
        } else {
            alert(result.message || "በቂ ሂሳብ የሎትም!");
            btnAction.disabled = false;
            toggleStepper(false);
        }
    } catch (e) {
        console.error(e);
        btnAction.disabled = false;
        toggleStepper(false);
    }
}

// ጨዋታን ለማቆም
async function endGame(isWon) {
    isPlaying = false;
    isGameOver = true;
    cancelAnimationFrame(animationFrameId);

    btnAction.disabled = true;

    if (isWon) {
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
                alert(`እንኳን ደስ አሎት! በ ${multiplier.toFixed(2)}x አቁመው ETB ${result.win_amount} አሸንፈዋል! 🎉`);
                const balanceEl = document.getElementById('balanceDisplay') || document.getElementById('balance');
                if (balanceEl) balanceEl.innerText = result.new_balance.toFixed(2) + " ETB";
            }
        } catch (e) {
            console.error(e);
        }
    } else {
        // ክራሽ ሲሆን ሮኬት ይፈነዳል
        playSound("crash");
        multiplierDisplay.innerText = "CRASHED!💥";
        ctx.fillStyle = "#ff0055";
        ctx.font = "bold 30px 'Segoe UI'";
        ctx.textAlign = "center";
        ctx.fillText(`FLEW AWAY @ ${multiplier.toFixed(2)}x`, canvas.width / 2, canvas.height / 2);
    }

    // ቁልፉን ወደ መጀመሪያው መመለስ
    setTimeout(() => {
        btnAction.disabled = false;
        btnAction.className = "action-btn bet-mode";
        btnAction.innerText = "ውርርድ ፍጠር (START)";
        btnAction.style.display = "block";
        toggleStepper(false);
    }, 1200);
}

// በተን ክሊክ
btnAction.addEventListener("click", function() {
    if (!isPlaying) {
        startGame();
    } else {
        endGame(true);
    }
});
