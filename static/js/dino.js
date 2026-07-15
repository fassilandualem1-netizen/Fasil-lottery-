// የጨዋታው መሠረታዊ ነገሮች ማግኛ
const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const multiplierDisplay = document.getElementById("multiplierDisplay");
const betAmountInput = document.getElementById("betAmount");
const btnStart = document.getElementById("btnStart");
const btnCashout = document.getElementById("btnCashout");

// የጨዋታው ሁኔታዎች (Game States)
let isPlaying = false;
let isGameOver = false;
let gameSpeed = 5;
let score = 0;
let multiplier = 1.00;
let animationFrameId;

// 1. የዘንዶው (Dino) ባህሪያት
const dino = {
    x: 50,
    y: 200,
    width: 40,
    height: 50,
    gravity: 0.6,
    velocity: 0,
    jumpStrength: -12,
    isJumping: false,
    
    draw() {
        // ቀላልና ቆንጆ ዘንዶ በካንቫስ መሳል
        ctx.fillStyle = "#00ffcc"; // አረንጓዴ/ኒዮን ዘንዶ
        ctx.fillRect(this.x, this.y, this.width, this.height);
        
        // አይን
        ctx.fillStyle = "#111";
        ctx.fillRect(this.x + 25, this.y + 10, 5, 5);
        
        // ጅራት
        ctx.fillStyle = "#00ddaa";
        ctx.beginPath();
        ctx.moveTo(this.x, this.y + this.height - 10);
        ctx.lineTo(this.x - 15, this.y + this.height - 5);
        ctx.lineTo(this.x, this.y + this.height);
        ctx.fill();
    },
    
    update() {
        // የመሳብ ኃይል (Gravity) መቆጣጠሪያ
        this.velocity += this.gravity;
        this.y += this.velocity;
        
        // መሬት ላይ መቆሙን ማረጋገጫ (የመሬቱ ቁመት 250px ነው)
        if (this.y > 250 - this.height) {
            this.y = 250 - this.height;
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
        this.y = 210; // መሬት ላይ እንዲቀመጥ
        this.width = 20 + Math.random() * 20; // የተለያየ ውፍረት
        this.height = 30 + Math.random() * 20; // የተለያየ ቁመት
    }
    
    draw() {
        ctx.fillStyle = "#e94560"; // ቀይ መሰናክል (ቁልቋል መሰል)
        ctx.fillRect(this.x, this.y + (40 - this.height), this.width, this.height);
    }
    
    update() {
        this.x -= gameSpeed;
    }
}

// 3. መሬቱን የሚስል ፈንክሽን
function drawGround() {
    ctx.strokeStyle = "#30304a";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(0, 250);
    ctx.lineTo(canvas.width, 250);
    ctx.stroke();
}

// 4. ሁለቱ ነገሮች መጋጨታቸውን ማወቂያ (Collision Detection)
function checkCollision(rect1, rect2) {
    return (
        rect1.x < rect2.x + rect2.width &&
        rect1.x + rect1.width > rect2.x &&
        rect1.y < rect2.y + (40 - rect2.height) + rect2.height &&
        rect1.y + rect1.height > rect2.y + (40 - rect2.height)
    );
}

// 5. የጨዋታው ዑደት (Game Loop)
function gameLoop() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    drawGround();
    
    // ዘንዶውን አዘምንና ሳል
    dino.update();
    dino.draw();
    
    // Multiplier ማሳደግ
    if (isPlaying) {
        multiplier += 0.005; // ፍጥነቱን እዚህ ማስተካከል ትችላለህ
        multiplierDisplay.innerText = multiplier.toFixed(2) + "x";
        btnCashout.innerText = `Cash Out (ETB ${(betAmountInput.value * multiplier).toFixed(2)}) 💰`;
    }
    
    // መሰናክሎችን መፍጠር (በየተወሰነ ጊዜ)
    if (Math.random() < 0.015 && obstacles.length === 0 || (obstacles.length > 0 && canvas.width - obstacles[obstacles.length - 1].x > 250)) {
        obstacles.push(new Obstacle());
    }
    
    // መሰናክሎችን ማንቀሳቀስና መሳል
    for (let i = obstacles.length - 1; i >= 0; i--) {
        obstacles[i].update();
        obstacles[i].draw();
        
        // ከዘንዶው ጋር መጋጨቱን መፈተሻ
        if (checkCollision(dino, obstacles[i])) {
            endGame(false); // ተጋጨ! ተሸነፈ
            return;
        }
        
        // ከስክሪን የወጡትን መሰናክሎች ማጥፊያ
        if (obstacles[i].x + obstacles[i].width < 0) {
            obstacles.splice(i, 1);
        }
    }
    
    // የጨዋታ ፍጥነትን በጊዜ ሂደት መጨመር
    gameSpeed += 0.001;
    
    animationFrameId = requestAnimationFrame(gameLoop);
}

// 6. ጨዋታ ለመጀመር
function startGame() {
    const betAmount = parseFloat(betAmountInput.value);
    if (isNaN(betAmount) || betAmount <= 0) {
        alert("እባክዎ ትክክለኛ የውርርድ መጠን ያስገቡ!");
        return;
    }
    
    // የ UI ለውጦች
    isPlaying = true;
    isGameOver = false;
    multiplier = 1.00;
    gameSpeed = 5;
    obstacles = [];
    dino.y = 200;
    dino.velocity = 0;
    
    btnStart.disabled = true;
    betAmountInput.disabled = true;
    btnCashout.style.display = "inline-block";
    btnCashout.disabled = false;
    
    gameLoop();
}

// 7. ጨዋታን ለማቆም (ማሸነፍ ወይም መሸነፍ)
function endGame(isWon) {
    isPlaying = false;
    isGameOver = true;
    cancelAnimationFrame(animationFrameId);
    
    btnStart.disabled = false;
    betAmountInput.disabled = false;
    btnCashout.style.display = "none";
    
    if (isWon) {
        // አሸንፏል (Cash Out አድርጓል)
        const finalWin = (betAmountInput.value * multiplier).toFixed(2);
        alert(`እንኳን ደስ አሎት! በ ${multiplier.toFixed(2)}x አቁመው ETB ${finalWin} አሸንፈዋል! 🎉`);
    } else {
        // ተሸንፏል (ተጋጭቷል)
        multiplierDisplay.innerText = "BUSTED!💥";
        ctx.fillStyle = "rgba(233, 69, 96, 0.8)";
        ctx.font = "bold 30px 'Segoe UI'";
        ctx.textAlign = "center";
        ctx.fillText("ተጋጭተዋል! (Game Over)", canvas.width / 2, canvas.height / 2);
    }
}

// 8. የቁልፍ መቆጣጠሪያዎች (Event Listeners)
// ስክሪን ሲነካ ወይም Spacebar ሲጫን እንዲዘል ማድረግ
window.addEventListener("keydown", function(e) {
    if (e.code === "Space") {
        e.preventDefault(); // ገጹ ወደታች እንዳይንሸራተት
        if (isPlaying) {
            dino.jump();
        }
    }
});

// ለስልክ ተጠቃሚዎች የካንቫስ ሜዳውን ሲነኩት እንዲዘል ማድረግ
canvas.addEventListener("touchstart", function(e) {
    e.preventDefault();
    if (isPlaying) {
        dino.jump();
    }
});

btnStart.addEventListener("click", startGame);

btnCashout.addEventListener("click", function() {
    if (isPlaying) {
        endGame(true); // Cash Out በተሳካ ሁኔታ ተደረገ
    }
});

// የመጀመሪያውን ሜዳ ዝም ብሎ ለመሳል
drawGround();
