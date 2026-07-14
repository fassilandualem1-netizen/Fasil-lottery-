// --- 1. የቴሌግራም መነሻ እና ቅንጅቶች ---
const tg = window.Telegram.WebApp;
tg.expand();

const userData = tg.initDataUnsafe?.user || { id: "8488592165", first_name: "የሰፈር ልጅ" };
const userId = userData.id.toString();

let currentBalance = 0;
let activeGame = null;
let scene, camera, renderer, gameCube, animationFrameId;

let isGameOver = false;
let currentBetAmount = 0; // የገባው የብር መጠን መመዝገቢያ

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("user-name")) {
        document.getElementById("user-name").innerText = userData.first_name;
    }
    fetchBalance();
});

// ባላንስ ከሰርቨር ማምጫ
async function fetchBalance() {
    try {
        const res = await fetch('/api/get_balance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });
        const data = await res.json();
        if (data.status === "success") {
            currentBalance = data.balance;
            const balEl = document.getElementById("user-balance") || document.getElementById("horse-game-balance");
            if (balEl) balEl.innerText = currentBalance.toFixed(2);
        }
    } catch (e) { console.error("ባላንስ ማግኘት አልተቻለም", e); }
}

// --- 2. 3D የአይጥ ጨዋታ እና የፈረስ ማስነሻ ሎጂክ ---
async function launchGame(gameType) {
    const betInput = document.getElementById("bet-amount") || document.getElementById("horse-bet-amount");
    const betAmount = betInput ? parseFloat(betInput.value || 0) : 0;

    if (betAmount <= 0) {
        return alert("እባክዎ መጀመሪያ ትክክለኛ የብር መጠን ያስገቡ!");
    }
    if (betAmount > currentBalance) {
        return alert("ይቅርታ፣ ያስገቡት የብር መጠን ካለዎት ባላንስ ይበልጣል!");
    }

    // የፈረስ ውድድር ከሆነ ወደ ተለየው የፈረስ ገጽ መምራት ወይም እዚያው ማስተናገድ ይቻላል
    if (gameType === 'horse' || gameType === 'horse_race') {
        window.location.href = '/horse_race.html'; 
        return;
    }

    try {
        // ለ3D አይጥ ጨዋታ ሰርቨር ላይ ጨዋታውን ማስጀመር
        const res = await fetch('/api/start_game', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, game_type: gameType, bet_amount: betAmount })
        });
        const data = await res.json();

        if (data.status === "ready") {
            currentBetAmount = betAmount;
            activeGame = gameType;
            isGameOver = false;
            
            document.getElementById("game-canvas-container").style.display = "block";
            fetchBalance(); 
            init3DWorld(gameType);
        } else {
            alert(data.message || "ጨዋታውን ማስጀመር አልተቻለም!");
        }
    } catch (e) { 
        alert("ከሰርቨር ጋር መገናኘት አልተቻለም። ለሙከራ ያህል በነፃ ይከፈታል!");
        activeGame = gameType;
        isGameOver = false;
        document.getElementById("game-canvas-container").style.display = "block";
        init3DWorld(gameType);
    }
}

// የ3D ጨዋታ ውጤትን ለሰርቨር ማሳወቂያ
async function sendGameResult(score, winStatus) {
    try {
        const res = await fetch('/api/end_game', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                user_id: userId, 
                game_type: activeGame, 
                score: score, 
                status: winStatus, 
                bet_amount: currentBetAmount 
            })
        });
        const data = await res.json();
        if (data.message) alert(data.message);
    } catch (e) { 
        console.error("ውጤት መላክ አልተቻለም", e); 
    }
    fetchBalance(); 
}

// 3D አለም መፍጠሪያ (ለአይጥ ጨዋታ ብቻ)
function init3DWorld(gameType) {
    const container = document.getElementById("game-canvas-container");

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x111827); // ይበልጥ ማራኪ ጥቁር ባክግራውንድ

    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    container.appendChild(renderer.domElement);

    // የአይጥ (የአይብ) ምስል ሊንክ
    let imageUrl = 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Visual_Studio_Code_Cheese_Icon.svg/512px-Visual_Studio_Code_Cheese_Icon.svg.png';

    const textureLoader = new THREE.TextureLoader();
    const gameTexture = textureLoader.load(imageUrl);
    const material = new THREE.SpriteMaterial({ map: gameTexture });
    
    gameCube = new THREE.Sprite(material);
    gameCube.scale.set(1.5, 1.5, 1.5);
    gameCube.position.set(0, 0, 0);
    scene.add(gameCube);

    const ambientLight = new THREE.AmbientLight(0xffffff, 1);
    scene.add(ambientLight);

    camera.position.set(0, 0, 4); 
    animate();
}

// የአኒሜሽን ሉፕ
function animate() {
    if (isGameOver) return;
    
    animationFrameId = requestAnimationFrame(animate);
    
    if (gameCube && (activeGame === 'mouse' || activeGame === 'የአይጥ ጨዋታ 3D')) {
        // አይጡ በስክሪኑ ላይ ወደ ግራና ቀኝ በሳይን ሞገድ እንዲወዛወዝ ማድረግ
        gameCube.position.x = Math.sin(Date.now() * 0.005) * 1.2;
    }
    
    renderer.render(scene, camera);
}

function exitGame() {
    cancelAnimationFrame(animationFrameId);
    activeGame = null;
    isGameOver = true;
    document.getElementById("game-canvas-container").style.display = "none";
    const container = document.getElementById("game-canvas-container");
    const canvas = container.querySelector("canvas");
    if (canvas) container.removeChild(canvas);
    fetchBalance();
}

// --- 3. ዘውድና ጎፈር (Coin Flip) ሎጂክ ---
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
        fetchBalance();
    } catch (e) { 
        alert("የሳንቲም ጨዋታው ሰርቨር ላይ አልተገኘም!"); 
    }
}

// የስክሪን መጠን ሲቀያየር 3D ውን ማስተካከያ
window.addEventListener('resize', () => {
    if (camera && renderer) {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    }
});
