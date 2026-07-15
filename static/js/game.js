// --- 1. የቴሌግራም መነሻ እና ቅንጅቶች ---
const tg = window.Telegram.WebApp;
tg.expand();

const userData = tg.initDataUnsafe?.user || { id: "8488592165", first_name: "የሰፈር ልጅ" };
const userId = userData.id.toString();

let currentBalance = 0;

// ገጹ ሲጫን የሚሰሩ ስራዎች
document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("user-name")) {
        document.getElementById("user-name").innerText = userData.first_name;
    }
    // 1. ባላንስ መጫኛ
    fetchBalance();
    
    // 2. የዕለቱ ሩሌት ሰዓት መቆጣጠሪያ ማስጀመሪያ
    updateWheelCooldown();
});

// ባላንስ ከሰርቨር ማምጫ (ያለ ሪሎድ ባላንሱን በራስ-ሰር ያዘምናል)
async function fetchBalance() {
    try {
        const res = await fetch('/api/get_balance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });
        const data = await res.json();
        if (data.status === "success") {
            const newBalance = data.balance;
            const balEl = document.getElementById("user-balance");
            
            if (balEl && newBalance !== currentBalance) {
                balEl.innerText = newBalance.toFixed(2);
                
                // በአረንጓዴ ቀለም አብርቶ እንዲጠፋ ማድረግ (Visual Effect)
                balEl.style.transition = "color 0.5s";
                balEl.style.color = "#2ed573";
                setTimeout(() => { balEl.style.color = "inherit"; }, 1500);
            }
            currentBalance = newBalance;
        }
    } catch (e) { 
        console.error("ባላንስ ማግኘት አልተቻለም", e); 
    }
}

// --- 2. ዘውድና ጎፈር (Coin Flip) ሎጂክ ---
async function triggerCoinFlip(choice) {
    const betInput = document.getElementById("bet-amount");
    const betAmount = betInput ? parseFloat(betInput.value || 0) : 0;
    
    if (betAmount <= 0) return alert("እባክዎ መጀመሪያ ትክክለኛ የብር መጠን ያስገቡ!");
    if (betAmount > currentBalance) return alert("ይቅርታ፣ ውርርድ ለማስያዝ በቂ ባላንስ የለዎትም!");

    try {
        const res = await fetch('/api/coin_flip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, choice: choice, bet_amount: betAmount })
        });
        const data = await res.json();
        alert(data.message);
        fetchBalance(); // ከጨዋታው በኋላ ባላንሱን ወዲያውኑ ያዘምናል
    } catch (e) { 
        alert("የሳንቲም ጨዋታው ሰርቨር ላይ አልተገኘም!"); 
    }
}

// --- 3. የዕለቱ ነጻ ዕድል ሩሌት ሎጂክ ---
const wheelSegments = [
    { angle: 30, text: "1 ብር", value: 1 },
    { angle: 90, text: "2 ብር", value: 2 },
    { angle: 150, text: "5 ብር", value: 5 },
    { angle: 210, text: "ባዶ", value: 0 },
    { angle: 270, text: "3 ብር", value: 3 },
    { angle: 330, text: "4 ብር", value: 4 }
];

let isWheelSpinning = false;
let wheelCooldownInterval;

// የሰዓት ቆጠራውን መቆጣጠሪያና ቁልፍ ማድረጊያ
function updateWheelCooldown() {
    const spinBtn = document.getElementById("spin-wheel-btn");
    const statusEl = document.getElementById("wheel-status");
    
    if (!spinBtn) return;
    if (wheelCooldownInterval) clearInterval(wheelCooldownInterval);

    wheelCooldownInterval = setInterval(() => {
        const lastSpin = localStorage.getItem("last_spin_" + userId);
        
        if (!lastSpin) {
            clearInterval(wheelCooldownInterval);
            spinBtn.disabled = false;
            spinBtn.innerText = "ሩሌቱን አሽከርክር";
            spinBtn.style.backgroundColor = "var(--success-color)";
            spinBtn.style.cursor = "pointer";
            if (statusEl) statusEl.innerText = "";
            return;
        }

        const now = Date.now();
        const nextSpinTime = parseInt(lastSpin) + (24 * 60 * 60 * 1000); // 24 ሰዓት
        const timeLeft = nextSpinTime - now;

        if (timeLeft <= 0) {
            clearInterval(wheelCooldownInterval);
            localStorage.removeItem("last_spin_" + userId);
            spinBtn.disabled = false;
            spinBtn.innerText = "ሩሌቱን አሽከርክር";
            spinBtn.style.backgroundColor = "var(--success-color)";
            spinBtn.style.cursor = "pointer";
            if (statusEl) statusEl.innerText = "";
        } else {
            spinBtn.disabled = true;
            spinBtn.style.backgroundColor = "#555";
            spinBtn.style.cursor = "not-allowed";

            const hours = Math.floor(timeLeft / (1000 * 60 * 60));
            const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);

            const timeString = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            spinBtn.innerText = `🔒 ተቆልፏል (${timeString})`;
            if (statusEl) {
                statusEl.innerHTML = `<span style="color: #e74c3c; font-size: 0.85rem;">⚠️ ይህንን ዕድል በቀን አንድ ጊዜ ብቻ መጠቀም ይችላሉ!</span>`;
            }
        }
    }, 1000);
}

// ሩሌቱን የማሽከርከር ሎጂክ
async function spinDailyWheel() {
    if (isWheelSpinning) return;

    const lastSpin = localStorage.getItem("last_spin_" + userId);
    if (lastSpin) {
        const timeLeft = parseInt(lastSpin) + (24 * 60 * 60 * 1000) - Date.now();
        if (timeLeft > 0) return alert("እባክዎ የሰዓት ገደቡ እስኪያልቅ ይጠብቁ!");
    }

    isWheelSpinning = true;
    const spinBtn = document.getElementById("spin-wheel-btn");
    const wheel = document.getElementById("bonus-wheel");
    const statusEl = document.getElementById("wheel-status");

    if (spinBtn) spinBtn.disabled = true;
    if (statusEl) statusEl.innerText = "ዕድልዎን በመፈለግ ላይ...";

    const prizeIndex = Math.floor(Math.random() * wheelSegments.length);
    const selectedPrize = wheelSegments[prizeIndex];

    const extraSpins = 5; 
    const targetAngle = selectedPrize.angle;
    const finalRotation = (extraSpins * 360) - targetAngle;

    if (wheel) {
        wheel.style.transform = `rotate(${finalRotation}deg)`;
    }

    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('medium');
    }

    setTimeout(async () => {
        isWheelSpinning = false;

        if (selectedPrize.value > 0) {
            if (statusEl) {
                statusEl.innerHTML = `<span style="color: #2ed573; font-size: 1.1rem;">🎉 እንኳን ደስ አለዎት! +${selectedPrize.text} አሸንፈዋል!</span>`;
            }
            
            // የዋሌት ባላንሱን ወዲያውኑ በራስ-ሰር ማሳደግ (NO RELOAD!)
            currentBalance += selectedPrize.value;
            const balEl = document.getElementById("user-balance");
            if (balEl) {
                balEl.innerText = currentBalance.toFixed(2);
                balEl.style.transition = "color 0.5s";
                balEl.style.color = "#2ed573";
                setTimeout(() => { balEl.style.color = "inherit"; }, 1500);
            }

            try {
                await fetch('/api/claim_daily_bonus', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId, amount: selectedPrize.value })
                });
            } catch (e) {
                console.error("ቦነሱን ሰርቨር ላይ ማስቀመጥ አልተቻለም", e);
            }
            
        } else {
            if (statusEl) {
                statusEl.innerHTML = `<span style="color: #ff4757; font-size: 1rem;">😢 ባዶ ወጥቷል! ነገ በድጋሚ ይሞክሩ።</span>`;
            }
        }

        // ሰዓቱን መመዝገብና ማስቆጠር መጀመር
        localStorage.setItem("last_spin_" + userId, Date.now().toString());
        updateWheelCooldown();

    }, 4000); 
}
