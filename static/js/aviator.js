// ==========================================
// 1. መሠረታዊ ማዋቀሪያዎች (Global & Telegram Setup)
// ==========================================
let tg = window.Telegram.WebApp;
tg.expand(); // ቴሌግራም ላይ ሙሉ ስክሪን እንዲሆን
tg.ready();

// ደህንነቱ የተጠበቀ የቴሌግራም ዳታ ለ Backend
const INIT_DATA = tg.initData || ""; 
let USER_ID = tg.initDataUnsafe?.user?.id || "test_user"; 
let USER_NAME = tg.initDataUnsafe?.user?.first_name || "Player";

// Socket ኔምስፔስ እና ማገናኛ
const socket = io('/aviator', { 
    reconnection: true, 
    reconnectionAttempts: 10,
    reconnectionDelay: 2000
});

let currentGameState = "WAITING"; 
let currentMultiplier = 1.00;
let flightStartTime = 0;
let animationFrameId;

// ==========================================
// 2. የድምፅ ማቀናበሪያ (Audio System)
// ==========================================
const sounds = {
    start: new Audio('/static/sounds/plane-start.mp3'),
    fly: new Audio('/static/sounds/flying.mp3'),
    crash: new Audio('/static/sounds/crash.mp3'),
    win: new Audio('/static/sounds/win.mp3')
};

// ብሮውዘር ድምፅን ብሎክ እንዳያደርግ (User Interaction ሲኖር ብቻ እንዲሰራ)
sounds.fly.loop = true; 
function playSound(type) {
    try {
        if(type === 'fly') sounds.fly.play().catch(e => console.log("Audio play prevented"));
        else if(type === 'stop_fly') { sounds.fly.pause(); sounds.fly.currentTime = 0; }
        else {
            let s = sounds[type].cloneNode(); // ድምፆች ቢደራረቡም እንዲሰሩ
            s.play().catch(e => console.log("Audio play prevented"));
        }
    } catch(e) {}
}

// ==========================================
// 3. የውርርድ ፓኔል መቆጣጠሪያ (Bet Panel Class)
// ==========================================
class BetPanel {
    constructor(panelId) {
        this.panelId = panelId; 
        this.state = 'IDLE';    
        this.isAutoBet = false;
        this.autoCashoutValue = 0; 

        this.button = document.getElementById(`${panelId}-btn`);
        this.amountInput = document.getElementById(`${panelId}-amount`);
        
        if(this.button) {
            this.button.addEventListener('click', () => {
                // User interaction ሲኖር ኦዲዮ አሎው እንዲሆን (Browser policy)
                if(sounds.win.currentTime === 0) sounds.win.load(); 
                this.handleButtonClick();
            });
        }
    }

    getCurrentAmount() {
        return parseFloat(this.amountInput.value) || 20.00;
    }

    handleButtonClick() {
        if (!socket.connected) {
            alert("ግንኙነት ተቋርጧል! እባክዎ ኢንተርኔትዎን ይፈትሹ።");
            return;
        }

        if (this.state === 'IDLE') {
            if (currentGameState === 'WAITING') this.placeBet('CURRENT'); 
            else if (currentGameState === 'FLYING') this.placeBet('NEXT');    
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
        let prevText = this.button.innerHTML;
        this.updateUI('Loading...', '#6c757d'); // Disable-like color
        this.button.disabled = true;
        
        try {
            let response = await fetch('/api/aviator/place_bet', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-Telegram-Init-Data': INIT_DATA // Security Validation!
                },
                body: JSON.stringify({ user_id: USER_ID, amount: betAmount })
            });
            let data = await response.json();

            this.button.disabled = false;

            if (data.status === 'success') {
                if (data.type === 'CURRENT' || roundType === 'CURRENT') {
                    this.state = 'BET_PLACED';
                    this.updateUI('CANCEL', '#dc3545', ''); 
                } else {
                    this.state = 'QUEUED';
                    this.updateUI('CANCEL', '#dc3545', '(Next Round)'); 
                }
            } else {
                this.showErrorToast(data.message || "ውርርድ አልተሳካም!"); 
                this.updateUI('BET', '#28a745', betAmount + ' ETB'); 
            }
        } catch (error) {
            this.button.disabled = false;
            this.showErrorToast("የኔትዎርክ ችግር አጋጥሟል!");
            this.updateUI('BET', '#28a745', betAmount + ' ETB');
        }
    }

    async cashOut() {
        this.button.disabled = true;
        try {
            let response = await fetch('/api/aviator/cashout', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-Telegram-Init-Data': INIT_DATA 
                },
                body: JSON.stringify({ user_id: USER_ID, current_multi: currentMultiplier.toFixed(2) })
            });
            let data = await response.json();
            this.button.disabled = false;

            if (data.status === 'success') {
                this.state = 'IDLE';
                let betAmount = this.getCurrentAmount();
                this.updateUI('BET', '#28a745', betAmount + ' ETB');
                
                playSound('win');
                showWinAnimation(data.win_amount, data.multiplier);
            }
        } catch (error) {
            this.button.disabled = false;
            this.showErrorToast("Cashout አልተሳካም!");
        }
    }

    cancelBet() {
        let betAmount = this.getCurrentAmount();
        this.state = 'IDLE';
        this.updateUI('BET', '#28a745', betAmount + ' ETB');
    }

    updateUI(text, bgColor, subText = "") {
        this.button.style.backgroundColor = bgColor;
        this.button.style.color = bgColor === '#ffc107' ? "black" : "white";
        if (subText) {
            this.button.innerHTML = `<span style="display:block; font-weight:bold;">${text}</span><span style="font-size: 14px;">${subText}</span>`;
        } else {
            this.button.innerHTML = `<span style="font-weight:bold;">${text}</span>`;
        }
    }

    showErrorToast(msg) {
        tg.showAlert(msg); // ቴሌግራም Native Alert
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

const panel1 = new BetPanel('p1');
const panel2 = new BetPanel('p2'); 

// ==========================================
// 4. የአውሮፕላኑ ሞተር (Animation & Sync)
// ==========================================
const multiplierDisplay = document.getElementById("multiplier-text");
const planeAnim = document.querySelector('.plane-anim'); 

function updateFlightAnimation() {
    if (currentGameState !== 'FLYING') return;

    // Latency Sync: ቆጣሪው ከጀመረበት ጊዜ ጋር በትክክል ማስላት
    let elapsedTime = (Date.now() - flightStartTime) / 1000;
    
    // ባክኤንዱ (Python) የሚጠቀመውን ተመሳሳይ ፎርሙላ እዚህም እንጠቀማለን
    currentMultiplier = Math.exp(0.06 * elapsedTime);
    
    // UI ማደስ
    multiplierDisplay.innerText = currentMultiplier.toFixed(2) + "x";
    multiplierDisplay.style.color = "white"; 
    
    panel1.checkAutoCashout(currentMultiplier);
    panel2.checkAutoCashout(currentMultiplier);

    animationFrameId = requestAnimationFrame(updateFlightAnimation);
}

// ==========================================
// 5. WebSocket አድማጭ (Server Comms & History)
// ==========================================

socket.on('connect', () => {
    console.log("Connected to server");
});

socket.on('disconnect', () => {
    console.log("Disconnected. Reconnecting...");
    // ዲስኮኔክት ሲያደርግ እንዳይጫወቱ መቆለፍ
});

socket.on('game_state', (data) => {
    currentGameState = data.status;

    panel1.onGameStateChange(currentGameState);
    panel2.onGameStateChange(currentGameState);

    if (currentGameState === 'WAITING') {
        cancelAnimationFrame(animationFrameId);
        playSound('stop_fly');
        multiplierDisplay.innerText = "WAITING...\n" + (data.time_left || "0") + "s"; 
        multiplierDisplay.style.color = "#ffc107"; 
        planeAnim.style.opacity = '0.1';
    } 
    else if (currentGameState === 'FLYING') {
        playSound('start');
        setTimeout(() => playSound('fly'), 500); 

        // Sync ቴክኒክ፡ የሰርቨሩን Elapsed Time ከተሰጠው ተጠቅመን የራሳችንን Start Time ማስተካከል
        let serverElapsedMs = (data.elapsed_time || 0) * 1000;
        flightStartTime = Date.now() - serverElapsedMs; 
        
        planeAnim.style.opacity = '1';
        
        if (!animationFrameId) {
            updateFlightAnimation(); 
        }
    } 
    else if (currentGameState === 'CRASHED') {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null; 
        playSound('stop_fly');
        playSound('crash');
        
        let crashPoint = data.crash_point ? parseFloat(data.crash_point).toFixed(2) : currentMultiplier.toFixed(2);
        multiplierDisplay.innerText = "CRASHED @ " + crashPoint + "x";
        multiplierDisplay.style.color = "#e50b2c"; 
        planeAnim.style.opacity = '0';

        // ታሪኩን (History) ማዘመን
        updateHistoryUI(crashPoint);
    }
});

// የ History ማሳያ ተግባር
function updateHistoryUI(newCrashPoint) {
    const historyBar = document.getElementById("history-bar"); // በ HTMLህ ውስጥ <div id="history-bar"> መኖር አለበት
    if(!historyBar) return;

    let span = document.createElement("span");
    span.innerText = newCrashPoint + "x";
    
    // በከለር መለየት (እንደ እውነተኛው አቪዬተር)
    let val = parseFloat(newCrashPoint);
    if (val < 2.0) span.style.color = "#3498db"; // ሰማያዊ
    else if (val < 10.0) span.style.color = "#9b59b6"; // ወይንጠጅ
    else span.style.color = "#e74c3c"; // ቀይ

    historyBar.prepend(span); // አዲሱን መጀመሪያ ላይ ማስገባት
    
    // ከ 20 በላይ ከሆኑ የድሮውን ማጥፋት
    if (historyBar.children.length > 20) {
        historyBar.removeChild(historyBar.lastChild);
    }
}

// አሸናፊ ሲሆን ፖፕ-አፕ (Visual Effect)
function showWinAnimation(amount, multiplier) {
    let winDiv = document.createElement('div');
    winDiv.className = 'win-toast'; // ለ CSS እንዲያመች
    winDiv.style.position = 'absolute';
    winDiv.style.top = '20%';
    winDiv.style.left = '50%';
    winDiv.style.transform = 'translate(-50%, -50%)';
    winDiv.style.backgroundColor = 'rgba(40, 167, 69, 0.9)';
    winDiv.style.color = 'white';
    winDiv.style.padding = '15px 30px';
    winDiv.style.borderRadius = '30px';
    winDiv.style.fontWeight = 'bold';
    winDiv.style.fontSize = '18px';
    winDiv.style.zIndex = '100';
    winDiv.style.boxShadow = '0px 0px 15px #28a745';
    winDiv.innerText = `You Won ${amount} ETB \n @ ${multiplier.toFixed(2)}x`;
    
    document.querySelector('.game-screen').appendChild(winDiv);
    setTimeout(() => { 
        winDiv.style.opacity = '0';
        winDiv.style.transition = 'opacity 0.5s';
        setTimeout(() => winDiv.remove(), 500); 
    }, 2500); 
}
