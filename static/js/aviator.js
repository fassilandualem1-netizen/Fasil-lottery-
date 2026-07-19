// ==========================================
// 1. መሠረታዊ ማዋቀሪያዎች (Global Setup)
// ==========================================
// ኔምስፔሱን ወደ Default ቀይረነዋል
const socket = io(); 
let tg = window.Telegram.WebApp;
let USER_ID = tg.initDataUnsafe?.user?.id || "test_user_123"; 

let currentGameState = "WAITING"; 
let currentMultiplier = 1.00;
let flightStartTime = 0;
let animationFrameId;

// ==========================================
// 2. የውርርድ ፓኔል መቆጣጠሪያ (Bet Panel Class)
// ==========================================
class BetPanel {
    constructor(panelId) {
        this.panelId = panelId; // አሁን 'p1' ወይም 'p2' ነው የሚሆነው
        this.state = 'IDLE';    
        this.isAutoBet = false;
        this.autoCashoutValue = 0; 

        // ከ HTML ጋር በትክክል ማሰር
        this.button = document.getElementById(`${panelId}-btn`);
        this.amountInput = document.getElementById(`${panelId}-amount`);
        
        if(this.button) {
            this.button.addEventListener('click', () => this.handleButtonClick());
        } else {
            console.error(`Button ${panelId}-btn not found!`);
        }
    }

    // አሁን ያለውን የብር መጠን ከ input ሳጥኑ ላይ ማንበብ
    getCurrentAmount() {
        return parseFloat(this.amountInput.value) || 20.00;
    }

    handleButtonClick() {
        if (this.state === 'IDLE') {
            if (currentGameState === 'WAITING') {
                this.placeBet('CURRENT'); 
            } else if (currentGameState === 'FLYING') {
                this.placeBet('NEXT');    
            }
        } 
        else if (this.state === 'ACTIVE' && currentGameState === 'FLYING') {
            this.cashOut(); 
        }
        else if (this.state === 'BET_PLACED' || this.state === 'QUEUED') {
            this.cancelBet();
        }
    }

    async placeBet(roundType) {
        let betAmount = this.getCurrentAmount();
        this.button.innerText = "Loading...";
        
        try {
            // ማሳሰቢያ፡ ይህ ራውት በ Flask (aviator.py) ውስጥ መኖሩን አረጋግጥ
            let response = await fetch('/api/aviator/place_bet', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: USER_ID, amount: betAmount })
            });
            let data = await response.json();

            if (data.status === 'success') {
                if (data.type === 'CURRENT' || roundType === 'CURRENT') {
                    this.state = 'BET_PLACED';
                    this.updateUI('CANCEL', '#dc3545', ''); 
                } else {
                    this.state = 'QUEUED';
                    this.updateUI('CANCEL', '#dc3545', '(Next Round)'); 
                }
            } else {
                alert(data.message || "ውርርድ አልተሳካም!"); 
                this.updateUI('BET', '#28a745', betAmount + ' ETB'); 
            }
        } catch (error) {
            console.error("Bet Error:", error);
            this.updateUI('BET', '#28a745', betAmount + ' ETB');
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
                let betAmount = this.getCurrentAmount();
                this.updateUI('BET', '#28a745', betAmount + ' ETB');
                
                showWinAnimation(data.win_amount, data.multiplier);
            }
        } catch (error) {
            console.error("Cashout Error:", error);
        }
    }

    cancelBet() {
        let betAmount = this.getCurrentAmount();
        this.state = 'IDLE';
        this.updateUI('BET', '#28a745', betAmount + ' ETB');
    }

    updateUI(text, bgColor, subText = "") {
        this.button.style.backgroundColor = bgColor;
        this.button.style.color = "white";
        if (subText) {
            this.button.innerHTML = `<span>${text}</span><span style="font-size: 14px; font-weight: 400;">${subText}</span>`;
        } else {
            this.button.innerHTML = `<span>${text}</span>`;
        }
    }

    onGameStateChange(newState) {
        let betAmount = this.getCurrentAmount();
        if (newState === 'WAITING') {
            if (this.state === 'QUEUED') {
                this.state = 'BET_PLACED';
                this.updateUI('CANCEL', '#dc3545', '');
            } 
            else if (this.state === 'IDLE' && this.isAutoBet) {
                this.placeBet('CURRENT');
            }
        } 
        else if (newState === 'FLYING') {
            if (this.state === 'BET_PLACED') {
                this.state = 'ACTIVE';
                this.updateUI('CASH OUT', '#ffc107', ''); 
                this.button.style.color = "black"; // ለቢጫ ባክግራውንድ ጥቁር ጽሁፍ
            }
        }
        else if (newState === 'CRASHED') {
            if (this.state === 'ACTIVE' || this.state === 'BET_PLACED') {
                this.state = 'IDLE';
                this.updateUI('BET', '#28a745', betAmount + ' ETB');
            }
        }
    }

    checkAutoCashout(currentMulti) {
        if (this.state === 'ACTIVE' && this.autoCashoutValue > 0) {
            if (currentMulti >= this.autoCashoutValue) {
                this.cashOut();
            }
        }
    }
}

// ትልቁ ማስተካከያ፡ 'panel-1' የነበረው ወደ 'p1' ተቀይሯል!
const panel1 = new BetPanel('p1');
const panel2 = new BetPanel('p2'); 


// ==========================================
// 3. የአውሮፕላኑ ሞተር (The Math & Animation Engine)
// ==========================================
const multiplierDisplay = document.getElementById("multiplier-text");
const planeAnim = document.querySelector('.plane-anim'); // የጀርባ አኒሜሽን

function updateFlightAnimation() {
    if (currentGameState !== 'FLYING') return;

    let elapsedTime = (Date.now() - flightStartTime) / 1000;
    currentMultiplier = Math.exp(0.06 * elapsedTime);
    
    multiplierDisplay.innerText = currentMultiplier.toFixed(2) + "x";
    multiplierDisplay.style.color = "white"; 
    planeAnim.style.opacity = '0.3'; // ሲበር እንዲታይ

    panel1.checkAutoCashout(currentMultiplier);
    panel2.checkAutoCashout(currentMultiplier);

    animationFrameId = requestAnimationFrame(updateFlightAnimation);
}

// ==========================================
// 4. WebSocket አድማጭ (Server Sync)
// ==========================================
socket.on('game_state', (data) => {
    currentGameState = data.status;

    panel1.onGameStateChange(currentGameState);
    panel2.onGameStateChange(currentGameState);

    if (currentGameState === 'WAITING') {
        cancelAnimationFrame(animationFrameId);
        multiplierDisplay.innerText = "WAITING...\n" + (data.time_left || "") + "s"; 
        multiplierDisplay.style.color = "#ffc107"; 
        planeAnim.style.opacity = '0.1';
    } 
    else if (currentGameState === 'FLYING') {
        // አዲስ መብረር ሲጀምር ብቻ ቆጣሪውን እናስጀምረዋለን
        if (!animationFrameId || currentMultiplier === 1.00) {
            flightStartTime = Date.now(); 
            updateFlightAnimation(); 
        }
    } 
    else if (currentGameState === 'CRASHED') {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null; // ሪሴት
        currentMultiplier = 1.00;
        
        let crashPoint = data.crash_point ? data.crash_point.toFixed(2) : "1.00";
        multiplierDisplay.innerText = "CRASHED @ " + crashPoint + "x";
        multiplierDisplay.style.color = "#e50b2c"; 
        planeAnim.style.opacity = '0';
    }
});

// አሸናፊ ሲሆን ፖፕ-አፕ የሚያሳይ
function showWinAnimation(amount, multiplier) {
    let winDiv = document.createElement('div');
    winDiv.style.position = 'absolute';
    winDiv.style.top = '20%';
    winDiv.style.left = '50%';
    winDiv.style.transform = 'translate(-50%, -50%)';
    winDiv.style.backgroundColor = '#28a745';
    winDiv.style.color = 'white';
    winDiv.style.padding = '10px 20px';
    winDiv.style.borderRadius = '20px';
    winDiv.style.fontWeight = 'bold';
    winDiv.style.zIndex = '100';
    winDiv.innerText = `Won ${amount} ETB @ ${multiplier.toFixed(2)}x`;
    
    document.querySelector('.game-screen').appendChild(winDiv);
    setTimeout(() => { winDiv.remove(); }, 3000); 
}
