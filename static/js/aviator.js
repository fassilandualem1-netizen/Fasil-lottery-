// ==========================================
// 1. መሠረታዊ ማዋቀሪያዎች (Global Setup)
// ==========================================
const socket = io('/aviator'); // ከፓይተን ሰርቨር ጋር መገናኛ
let tg = window.Telegram.WebApp; // የቴሌግራም ዌብ አፕ ዳታ
let USER_ID = tg.initDataUnsafe?.user?.id || "test_user_123"; // በቴሌግራም ሲከፈት ትክክለኛውን አይዲ ይወስዳል

let currentGameState = "WAITING"; // WAITING, FLYING, CRASHED
let currentMultiplier = 1.00;
let flightStartTime = 0;
let animationFrameId;

// የድምፅ ኢፌክቶች (ካስፈለገህ)
// const flySound = new Audio('/sounds/fly.mp3'); 

// ==========================================
// 2. የውርርድ ፓኔል መቆጣጠሪያ (Bet Panel Class)
// ==========================================
class BetPanel {
    constructor(panelId) {
        this.panelId = panelId; // 'panel-1' ወይም 'panel-2'
        this.amount = 20.00;
        this.state = 'IDLE';    // IDLE, BET_PLACED, QUEUED, ACTIVE
        this.isAutoBet = false;
        this.autoCashoutValue = 0; // 0 ማለት ጠፍቷል ማለት ነው

        // የ HTML ኤለመንቶችን ማሰር
        this.button = document.getElementById(`${panelId}-btn`);
        this.amountInput = document.getElementById(`${panelId}-amount`);
        
        // ክሊክ ሲደረግ
        this.button.addEventListener('click', () => this.handleButtonClick());
    }

    // በተኑ ሲነካ ምን ይፈጠር? (ዋናው ሎጂክ)
    handleButtonClick() {
        if (this.state === 'IDLE') {
            if (currentGameState === 'WAITING') {
                this.placeBet('CURRENT'); // ለአሁኑ ዙር
            } else if (currentGameState === 'FLYING') {
                this.placeBet('NEXT');    // ለቀጣይ ዙር (Next Round)
            }
        } 
        else if (this.state === 'ACTIVE' && currentGameState === 'FLYING') {
            this.cashOut(); // ብር ማውጣት
        }
        else if (this.state === 'BET_PLACED' || this.state === 'QUEUED') {
            // Cancel ማድረግ (ገና ሳይበር ሀሳቡን ከቀየረ)
            this.cancelBet();
        }
    }

    // ወደ ባክኤንድ ኤፒአይ (Python) መረጃ መላክ
    async placeBet(roundType) {
        this.button.innerText = "Loading...";
        try {
            let response = await fetch('/api/aviator/place_bet', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: USER_ID, amount: this.amount })
            });
            let data = await response.json();

            if (data.status === 'success') {
                if (data.type === 'CURRENT') {
                    this.state = 'BET_PLACED';
                    this.updateUI('Cancel', '#dc3545'); // ቀይ Cancel
                } else if (data.type === 'NEXT') {
                    this.state = 'QUEUED';
                    this.updateUI('Cancel (Next Round)', '#dc3545'); // ቀይ Cancel
                }
            } else {
                alert(data.message); // ባላንስ ካጠረው
                this.updateUI(`Bet ${this.amount} ETB`, '#28a745'); // አረንጓዴ ይሁን
            }
        } catch (error) {
            console.error("Bet Error:", error);
        }
    }

    async cashOut() {
        try {
            let response = await fetch('/api/aviator/cashout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: USER_ID })
            });
            let data = await response.json();

            if (data.status === 'success') {
                this.state = 'IDLE';
                this.updateUI(`Bet ${this.amount} ETB`, '#28a745');
                
                // አሸነፍክ የሚል አኒሜሽን ስክሪኑ ላይ ማሳየት
                showWinAnimation(data.win_amount, data.multiplier);
            }
        } catch (error) {
            console.error("Cashout Error:", error);
        }
    }

    cancelBet() {
        // (Optional: እዚህ ጋር ወደ ባክኤንድ ኤፒአይ ልከህ ብሩን መመለስ ትችላለህ)
        this.state = 'IDLE';
        this.updateUI(`Bet ${this.amount} ETB`, '#28a745');
    }

    updateUI(text, bgColor) {
        this.button.innerText = text;
        this.button.style.backgroundColor = bgColor;
        this.button.style.color = "white";
    }

    // ጌሙ ስቴት ሲቀይር ፓኔሉ ራሱን የሚያስተካክልበት
    onGameStateChange(newState) {
        if (newState === 'WAITING') {
            if (this.state === 'QUEUED') {
                this.state = 'BET_PLACED';
                this.updateUI('Cancel', '#dc3545');
            } 
            // Auto Bet አብርቶ ከሆነ ራሱ ይጫወታል
            else if (this.state === 'IDLE' && this.isAutoBet) {
                this.placeBet('CURRENT');
            }
        } 
        else if (newState === 'FLYING') {
            if (this.state === 'BET_PLACED') {
                this.state = 'ACTIVE';
                this.updateUI(`Cash Out`, '#ffc107'); // ቢጫ ቀለም ብር ማውጫ
            }
        }
        else if (newState === 'CRASHED') {
            if (this.state === 'ACTIVE') {
                // ተበላ ማለት ነው
                this.state = 'IDLE';
                this.updateUI(`Bet ${this.amount} ETB`, '#28a745');
            }
        }
    }

    // ራሱ ቼክ እያደረገ Cash out የሚያደርግበት
    checkAutoCashout(currentMulti) {
        if (this.state === 'ACTIVE' && this.autoCashoutValue > 0) {
            if (currentMulti >= this.autoCashoutValue) {
                this.cashOut();
            }
        }
    }
}

// ሁለቱን ፓኔሎች ማስጀመር
const panel1 = new BetPanel('panel-1');
const panel2 = new BetPanel('panel-2'); // ኤችቲኤምኤል ላይ ሁለተኛ ፓኔል ካለህ


// ==========================================
// 3. የአውሮፕላኑ ሞተር (The Math & Animation Engine)
// ==========================================
const multiplierDisplay = document.getElementById("multiplier-text");

function updateFlightAnimation() {
    if (currentGameState !== 'FLYING') return;

    // አውሮፕላኑ ከተነሳ ያለፈውን ጊዜ (በሰከንድ) ማስላት
    let elapsedTime = (Date.now() - flightStartTime) / 1000;
    
    // ከፓይተኑ ጋር አንድ አይነት የሆነው የእድገት ቀመር (M = e^(0.06 * t))
    currentMultiplier = Math.exp(0.06 * elapsedTime);
    
    // ስክሪኑ ላይ ቁጥሩን መጻፍ
    multiplierDisplay.innerText = currentMultiplier.toFixed(2) + "x";
    multiplierDisplay.style.color = "white"; // እየበረረ ነጭ ነው

    // Auto cashout ቼክ ማድረግ (በየሚሊሰከንዱ)
    panel1.checkAutoCashout(currentMultiplier);
    panel2.checkAutoCashout(currentMultiplier);

    // ሪፍሬሽ ሲያደርግ ራሱን መልሶ ይጠራል (60 FPS)
    animationFrameId = requestAnimationFrame(updateFlightAnimation);
}

// ==========================================
// 4. WebSocket አድማጭ (Server Sync)
// ==========================================
socket.on('game_state', (data) => {
    currentGameState = data.status;

    // ፓኔሎቹን አፕዴት ማድረግ
    panel1.onGameStateChange(currentGameState);
    panel2.onGameStateChange(currentGameState);

    if (currentGameState === 'WAITING') {
        cancelAnimationFrame(animationFrameId);
        multiplierDisplay.innerText = "WAITING..."; // ወይም ፕሮግሬስ ባር ማሳየት
        multiplierDisplay.style.color = "#dc3545"; // ቀይ ቴክስት
    } 
    else if (currentGameState === 'FLYING') {
        // ሰርቨር እና ክላይንት ሰዓት እንዳይፋለስ የራሳችንን ቆጣሪ እንጀምራለን
        flightStartTime = Date.now(); 
        updateFlightAnimation(); // አኒሜሽኑን አስጀምር!
    } 
    else if (currentGameState === 'CRASHED') {
        cancelAnimationFrame(animationFrameId);
        // መከሰከሻውን ከሰርቨሩ እንደመጣ በትክክል ማሳየት
        multiplierDisplay.innerText = "Flew Away\n" + data.crash_point.toFixed(2) + "x";
        multiplierDisplay.style.color = "#dc3545"; // ክራሽ ሲያደርግ ቀይ ይሆናል
    }
});

// አሸናፊ ሲሆን ፖፕ-አፕ (Toast) የሚያሳይ ጌጥ
function showWinAnimation(amount, multiplier) {
    let winDiv = document.createElement('div');
    winDiv.className = "win-popup";
    winDiv.innerText = `You won ${amount} ETB at ${multiplier.toFixed(2)}x`;
    document.body.appendChild(winDiv);
    
    setTimeout(() => { winDiv.remove(); }, 3000); // ከ 3 ሰከንድ በኋላ ይጠፋል
}
