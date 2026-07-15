// የጨዋታው መሠረታዊ ነገሮች ማግኛ
const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const multiplierDisplay = document.getElementById("multiplierDisplay");
const betAmountInput = document.getElementById("betAmount");
const btnStart = document.getElementById("btnStart");
const btnCashout = document.getElementById("btnCashout");
const stepperBtns = document.querySelectorAll('.stepper-btn');

// የቴሌግራም ወብ አፕ ዳታ ማግኛ
const tg = window.Telegram ? window.Telegram.WebApp : null;
const userId = tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id.toString() : "8488592165";

// የጨዋታው ሁኔታዎች (Game States)
let isPlaying = false;
let isGameOver = false;
let gameSpeed = 6;
let multiplier = 1.00;
let animationFrameId;
let gameFrame = 0; // ለአኒሜሽን ፍሬም መቁጠሪያ

// 1. የዘንዶው (Dino) ባህሪያት
const dino = {
    x: 80,
    y: 320,
    width: 45,
    height: 55,
    gravity: 0.7,
    velocity: 0,
    jumpStrength: -14,
    isJumping: false,
    legPhase: 0, // ለእግር አኒሜሽን
    
    draw() {
        // የዲኖ አካል መሳል
        ctx.fillStyle = "#00ffcc";
        ctx.fillRect(this.x, this.y, this.width, this.height - 10);
        
        // ራስ (Head)
        ctx.fillRect(this.x + 10, this.y - 15, this.width - 10, 20);
        
        // አይን (Eye)
        ctx.fillStyle = "#111122";
        ctx.fillRect(this.x + 30, this.y - 10, 6, 6);
        
        // አፍ/ጥርሶች (Teeth)
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(this.x + 40, this.y + 2, 5, 4);

        // የእግር አኒሜሽን (ሲሮጥ እግሮቹ እንዲፈራረቁ ማድረግ)
        ctx.fillStyle = "#00ddaa";
        this.legPhase = Math.floor(gameFrame / 8) % 2;
        
        if (this.isJumping) {
            // ሲዘል እግሮቹ እጥፍ ይላሉ
            ctx.fillRect(this.x + 8, this.y + this.height - 10, 8, 8);
            ctx.fillRect(this.x + 28, this.y + this.height - 10, 8, 8);
        } else {
            // በሩጫ ሰዓት አንዱ እግር ወደ ታች ሌላኛው ወደ ላይ ይሆናል
            if (this.legPhase === 0) {
                ctx.fillRect(this.x + 8, this.y + this.height - 10, 8, 12); // እግር 1 ታች
                ctx.fillRect(this.x + 28, this.y + this.height - 10, 8, 6);  // እግር 2 ላይ
            } else {
                ctx.fillRect(this.x + 8, this.y + this.height - 10, 8, 6);   // እግር 1 ላይ
                ctx.fillRect(this.x + 28, this.y + this.height - 10, 8, 12);  // እግር 2 ታች
            }
        }
    },
    
    update() {
        this.velocity += this.gravity;
        this.y += this.velocity;
        
        // የመሬት መስመር ከፍታ 370px ነው
        if (this.y > 370 - this.height) {
            this.y = 370 - this.height;
            this.velocity = 0;
            this.isJumping = false;
        }
    },
    
    jump() {
        if (!this.isJumping) {
            this.velocity = this.jumpStrength;
            this.isJumping = true;
        }
    }
};

// 2. የመሰናክሎች (Obstacles) ባህሪያት
let obstacles = [];

class Obstacle {
    constructor() {
        this.x = canvas.width;
        this.width = 25 + Math.random() * 15;
        this.height = 40 + Math.random() * 25;
        this.y = 370 - this.height; // በትክክል መሬት ላይ እንዲቆም
    }
    
    draw() {
        // የቁልቋል (Cactus) ቅርጽ በካንቫስ መሳል
        ctx.fillStyle = "#ff0055"; // ቀይ/ኒዮን መሰናክል
        ctx.fillRect(this.x, this.y, this.width, this.height);
        
        // የግራ እጅጌ
        ctx.fillRect(this.x - 8, this.y + 10, 8, this.height / 2);
        ctx.fillRect(this.x - 8, this.y + 10, this.width / 2, 8);
        
        // የቀኝ እጅጌ
        ctx.fillRect(this.x + this.width, this.y + 15, 8, this.height / 2);
        ctx.fillRect(this.x + this.width - 5, this.y + 15, this.width / 2, 8);
    }
    
    update() {
        this.x -= gameSpeed;
    }
}

// 3. የበስተጀርባ ኮከቦች/የፍጥነት አቧራዎች (Stars/Speed Dust)
let dustParticles = [];
function updateDust() {
    if (Math.random() < 0.15) {
        dustParticles.push({
            x: canvas.width,
            y: Math.random() * 280,
            speed: gameSpeed * (0.5 + Math.random() * 0.5),
            size: 1 + Math.random() * 3
        });
    }
    ctx.fillStyle = "rgba(255, 255, 255, 0.4)";
    for (let i = dustParticles.length - 1; i >= 0; i--) {
        dustParticles[i].x -= dustParticles[i].speed;
        ctx.fillRect(dustParticles[i].x, dustParticles[i].y, dustParticles[i].size, dustParticles[i].size);
        if (dustParticles[i].x < 0) {
            dustParticles.splice(i, 1);
        }
    }
}

// 4. መሬቱን መሳያ
function drawGround() {
    // ዋናው የመሬት መስመር
    ctx.strokeStyle = "#30304a";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(0, 370);
    ctx.lineTo(canvas.width, 370);
    ctx.stroke();

    // መሬት ላይ ያሉ ትንንሽ ቋጥኞች/ሳሮች (የሩጫ ፍጥነት እንዲሰማ)
    ctx.fillStyle = "#30304a";
    for (let i = 0; i < canvas.width; i += 100) {
        let xOffset = (i - (gameFrame * gameSpeed) % 100);
        ctx.fillRect(xOffset, 374, 15, 4);
    }
}

// 5. የግጭት መቆጣጠሪያ
function checkCollision(rect1, rect2) {
    return (
        rect1.x < rect2.x + rect2.width &&
        rect1.x + rect1.width > rect2.x &&
        rect1.y < rect2.y + rect2.height &&
        rect1.y + rect1.height > rect2.y
    );
}

// 6. የ $+$ እና $-$ በተኖችን መቆለፊያ
function toggleStepperButtons(disabled) {
    stepperBtns.forEach(btn => {
        btn.disabled = disabled;
        btn.style.opacity = disabled ? "0.5" : "1";
        btn.style.cursor = disabled ? "not-allowed" : "pointer";
    });
}

// 7. የጨዋታው ዑደት (Game Loop)
function gameLoop() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    gameFrame++;
    
    // ከበስተጀርባ ያሉ አቧራዎችን ማሳየት
    updateDust();
    
    drawGround();
    
    // ዘንዶውን ማዘመን
    dino.update();
    dino.draw();
    
    // Multiplier በየሴኮንዱ ማሳደጊያ
    if (isPlaying) {
        multiplier += 0.005; 
        multiplierDisplay.innerText = multiplier.toFixed(2) + "x";
        btnCashout.innerText = `Cash Out (ETB ${(betAmountInput.value * multiplier).toFixed(2)}) 💰`;
    }
    
    // መሰናክል መፍጠር
    if (obstacles.length === 0 || (canvas.width - obstacles[obstacles.length - 1].x > 260 + Math.random() * 150)) {
        obstacles.push(new Obstacle());
    }
    
    // መሰናክሎችን ማንቀሳቀስ
    for (let i = obstacles.length - 1; i >= 0; i--) {
        obstacles[i].update();
        obstacles[i].draw();
        
        if (checkCollision(dino, obstacles[i])) {
            endGame(false); // ተሸነፈ
            return;
        }
        
        if (obstacles[i].x + obstacles[i].width < 0) {
            obstacles.splice(i, 1);
        }
    }
    
    gameSpeed += 0.001; // ፍጥነቱ ቀስ በቀስ ይጨምራል
    animationFrameId = requestAnimationFrame(gameLoop);
}

// 8. ጨዋታ ለመጀመር
async function startGame() {
    const betAmount = parseFloat(betAmountInput.value);
    if (isNaN(betAmount) || betAmount <= 0) {
        alert("እባክዎ ትክክለኛ የውርርድ መጠን ያስገቡ!");
        return;
    }
    
    btnStart.disabled = true; 
    toggleStepperButtons(true);
    
    try {
        const response = await fetch('/api/dino/bet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                user_id: userId,
                bet_amount: betAmount 
            })
        });
        const result = await response.json();
        
        if (result.status === "success") {
            isPlaying = true;
            isGameOver = false;
            multiplier = 1.00;
            gameSpeed = 6;
            obstacles = [];
            dustParticles = [];
            dino.y = 370 - dino.height;
            dino.velocity = 0;
            
            betAmountInput.disabled = true;
            btnCashout.style.display = "inline-block";
            btnCashout.disabled = false;
            
            // በሳይቱ ላይ ባላንስ ማሳያ ካለ ማደሻ
            const balanceEl = document.getElementById('balanceDisplay') || document.getElementById('balance');
            if (balanceEl) balanceEl.innerText = result.new_balance.toFixed(2) + " ETB";
            
            gameLoop();
        } else {
            alert(result.message || "ይቅርታ፣ በቂ ሂሳብ የሎትም!");
            btnStart.disabled = false;
            toggleStepperButtons(false);
        }
    } catch (error) {
        console.error("Error:", error);
        alert("የግንኙነት ችግር አጋጥሟል!");
        btnStart.disabled = false;
        toggleStepperButtons(false);
    }
}

// 9. ጨዋታን ለማቆም
async function endGame(isWon) {
    isPlaying = false;
    isGameOver = true;
    cancelAnimationFrame(animationFrameId);
    
    btnStart.disabled = false;
    betAmountInput.disabled = false;
    toggleStepperButtons(false);
    btnCashout.style.display = "none";
    
    if (isWon) {
        const betAmount = parseFloat(betAmountInput.value);
        btnCashout.disabled = true;
        
        try {
            const response = await fetch('/api/dino/cashout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    user_id: userId,
                    bet_amount: betAmount, 
                    multiplier: multiplier 
                })
            });
            const result = await response.json();
            
            if (result.status === "success") {
                alert(`እንኳን ደስ አሎት! በ ${multiplier.toFixed(2)}x አቁመው ETB ${result.win_amount} አሸንፈዋል! 🎉`);
                const balanceEl = document.getElementById('balanceDisplay') || document.getElementById('balance');
                if (balanceEl) balanceEl.innerText = result.new_balance.toFixed(2) + " ETB";
            }
        } catch (error) {
            console.error("Error During Cashout:", error);
            alert("የCash Out ስህተት ተፈጥሯል!");
        }
    } else {
        multiplierDisplay.innerText = "BUSTED!💥";
        ctx.fillStyle = "rgba(233, 69, 96, 0.85)";
        ctx.font = "bold 26px 'Segoe UI'";
        ctx.textAlign = "center";
        ctx.fillText("ተጋጭተዋል! (Game Over)", canvas.width / 2, canvas.height / 2);
    }
}

// 10. መቆጣጠሪያ ክስተቶች (Event Listeners)
window.addEventListener("keydown", function(e) {
    if (e.code === "Space") {
        e.preventDefault();
        if (isPlaying) {
            dino.jump();
        }
    }
});

canvas.addEventListener("touchstart", function(e) {
    e.preventDefault();
    if (isPlaying) {
        dino.jump();
    }
});

btnStart.addEventListener("click", startGame);

btnCashout.addEventListener("click", function() {
    if (isPlaying) {
        endGame(true);
    }
});

// የመጀመሪያውን ገጽታ መሳያ
drawGround();
