// ቴሌግራም ወብ አፕ ዳታ ማግኛ (Telegram WebApp User ID)
const tg = window.Telegram ? window.Telegram.WebApp : null;
const userId = tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id.toString() : "8488592165"; // ለሙከራ ካልተገኘ የአድሚን ID

// 6. ጨዋታ ለመጀመር (ከWallet ጋር ተገናኝቶ)
async function startGame() {
    const betAmount = parseFloat(betAmountInput.value);
    if (isNaN(betAmount) || betAmount <= 0) {
        alert("እባክዎ ትክክለኛ የውርርድ መጠን ያስገቡ!");
        return;
    }
    
    btnStart.disabled = true; // ድርብ ክሊክን ለመከላከል
    
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
            // ባላንስ በተሳካ ሁኔታ ከተቀነሰ ጨዋታው ይጀምራል
            isPlaying = true;
            isGameOver = false;
            multiplier = 1.00;
            gameSpeed = 5;
            obstacles = [];
            dino.y = 200;
            dino.velocity = 0;
            
            betAmountInput.disabled = true;
            btnCashout.style.display = "inline-block";
            btnCashout.disabled = false;
            
            // ካለህ የዌብሳይት ግድግዳ ላይ ባላንስ ማሳያ ካለ ማደስ ትችላለህ (ለምሳሌ: document.getElementById('balance').innerText = result.new_balance)
            
            gameLoop();
        } else {
            alert(result.message || "ይቅርታ፣ በቂ ሂሳብ የሎትም!");
            btnStart.disabled = false;
        }
    } catch (error) {
        console.error("Error:", error);
        alert("የግንኙነት ችግር አጋጥሟል!");
        btnStart.disabled = false;
    }
}

// 7. ጨዋታን ለማቆም (ማሸነፍ ወይም መሸነፍ)
async function endGame(isWon) {
    isPlaying = false;
    isGameOver = true;
    cancelAnimationFrame(animationFrameId);
    
    btnStart.disabled = false;
    betAmountInput.disabled = false;
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
                // ባላንስ ማሳያውን እዚህም በአዲሱ result.new_balance ማደስ ትችላለህ
            }
        } catch (error) {
            console.error("Error During Cashout:", error);
            alert("የCash Out ስህተት ተፈጥሯል!");
        }
    } else {
        multiplierDisplay.innerText = "BUSTED!💥";
        ctx.fillStyle = "rgba(233, 69, 96, 0.8)";
        ctx.font = "bold 30px 'Segoe UI'";
        ctx.textAlign = "center";
        ctx.fillText("ተጋጭተዋል! (Game Over)", canvas.width / 2, canvas.height / 2);
    }
}
