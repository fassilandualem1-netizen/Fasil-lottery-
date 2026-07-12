// --- 1. የቴሌግራም መነሻ ---
const tg = window.Telegram.WebApp;
tg.expand();

const userData = tg.initDataUnsafe?.user || { id: "8488592165", first_name: "የሰፈር ልጅ" };
const userId = userData.id.toString();

let currentBalance = 0;
let activeGame = null;
let scene, camera, renderer, gameCube, animationFrameId;

// የበግ ሩጫ ተለዋዋጮች
let asphaltRoad;
let obstacles = [];
let gameScore = 0;
let isGameOver = false;
let currentBetAmount = 0; // የገባው የብር መጠን መመዝገቢያ

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("user-name").innerText = userData.first_name;
    fetchBalance();
    
    // የንክኪ (Touch) ቁጥጥር
    window.addEventListener('touchstart', (e) => {
        if (!isGameOver && (activeGame === 'sheep' || activeGame === 'የበግ ሩጫ 3D')) {
            const touchX = e.touches[0].clientX;
            if (touchX < window.innerWidth / 2) {
                if (gameCube && gameCube.position.x > -1) gameCube.position.x -= 0.5;
            } else {
                if (gameCube && gameCube.position.x < 1) gameCube.position.x += 0.5;
            }
        }
    });
});

// ባላንስ ማምጫ
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
            document.getElementById("user-balance").innerText = currentBalance.toFixed(2);
        }
    } catch (e) { console.error("ባላንስ ማግኘት አልተቻለም", e); }
}

// --- 2. 3D ጨዋታ ማስነሻ (ከሂሳብ ሎጂክ ጋር የተገናኘ) ---
async function launchGame(gameType) {
    // 1. መጀመሪያ ተጫዋቹ ያስገባውን የብር መጠን ከ input ፎርም ላይ እናነባለን
    const betInput = document.getElementById("bet-amount");
    const betAmount = betInput ? parseFloat(betInput.value || 0) : 0;

    if (betAmount <= 0) {
        return alert("እባክዎ መጀመሪያ ትክክለኛ የብር መጠን ያስገቡ!");
    }
    if (betAmount > currentBalance) {
        return alert("ይቅርታ፣ ያስገቡት የብር መጠን ካለዎት ባላንስ ይበልጣል!");
    }

    try {
        // 2. ሰርቨሩ ላይ ጨዋታውን አስጀምረን ብሩን እንዲቀንስ እናደርጋለን
        const res = await fetch('/api/start_game', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, game_type: gameType, bet_amount: betAmount })
        });
        const data = await res.json();

        if (data.status === "ready") {
            // ብሩ በትክክል ከተቀነሰ 3D አለሙን እናስነሳለን
            currentBetAmount = betAmount;
            activeGame = gameType;
            isGameOver = false;
            gameScore = 0;
            obstacles = [];
            
            document.getElementById("game-canvas-container").style.display = "block";
            fetchBalance(); // አዲሱን የተቀነሰ ባላንስ ለማሳየት
            init3DWorld(gameType);
        } else {
            alert(data.message || "ጨዋታውን ማስጀመር አልተቻለም!");
        }
    } catch (e) { 
        alert("ከሰርቨር ጋር መገናኘት አልተቻለም። ለሙከራ ያህል በነፃ ይከፈታል!");
        // ሰርቨር ከሌለ ለሙከራ እንዲከፈት ካስፈለገ፡
        activeGame = gameType;
        isGameOver = false;
        gameScore = 0;
        obstacles = [];
        document.getElementById("game-canvas-container").style.display = "block";
        init3DWorld(gameType);
    }
}

// የጨዋታ ውጤትን ለሰርቨር ማሳወቂያ (አዲስ የተጨመረ የሂሳብ ሎጂክ)
async function sendGameResult(score, winStatus) {
    try {
        const res = await fetch('/api/end_game', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                user_id: userId, 
                game_type: activeGame, 
                score: score, 
                status: winStatus, // 'win' ወይም 'lose'
                bet_amount: currentBetAmount 
            })
        });
        const data = await res.json();
        if (data.message) alert(data.message);
    } catch (e) { 
        console.error("ውጤት መላክ አልተቻለም", e); 
    }
    fetchBalance(); // የደመወዝ ወይም የሽንፈት ባላንስ ማደሻ
}

// 3D አለም መፍጠሪያ
function init3DWorld(gameType) {
    const container = document.getElementById("game-canvas-container");

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x87CEEB); 

    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    container.appendChild(renderer.domElement);

    if (gameType === 'sheep' || gameType === 'የበግ ሩጫ 3D') {
        const roadGeo = new THREE.PlaneGeometry(3, 20);
        const roadMat = new THREE.MeshBasicMaterial({ color: 0x333333 }); 
        asphaltRoad = new THREE.Mesh(roadGeo, roadMat);
        asphaltRoad.rotation.x = -Math.PI / 2; 
        asphaltRoad.position.set(0, -1, -5);
        scene.add(asphaltRoad);
    }

    let imageUrl = '';
    if (gameType === 'sheep' || gameType === 'የበግ ሩጫ 3D') {
        imageUrl = 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Sheep_icon.svg/512px-Sheep_icon.svg.png';
    } else if (gameType === 'mouse' || gameType === 'የአይጥ ጨዋታ 3D') {
        imageUrl = 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Visual_Studio_Code_Cheese_Icon.svg/512px-Visual_Studio_Code_Cheese_Icon.svg.png';
    } else if (gameType === 'lion' || gameType === 'የአንበሳ አደን 3D') {
        imageUrl = 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/73/Lion_waiting_cartoon.svg/512px-Lion_waiting_cartoon.svg.png';
    }

    const textureLoader = new THREE.TextureLoader();
    const gameTexture = textureLoader.load(imageUrl);
    const material = new THREE.SpriteMaterial({ map: gameTexture });
    
    gameCube = new THREE.Sprite(material);
    gameCube.scale.set(1, 1, 1);
    
    if (gameType === 'sheep' || gameType === 'የበግ ሩጫ 3D') {
        gameCube.position.set(0, -0.5, 1); 
    } else {
        gameCube.position.set(0, 0, 0);
    }
    scene.add(gameCube);

    if (gameType === 'sheep' || gameType === 'የበግ ሩጫ 3D') {
        createObstacle('ባጃጅ', -10);
        createObstacle('ሲኖ ትራክ', -18);
        createObstacle('ሌባ', -25);
    }

    const ambientLight = new THREE.AmbientLight(0xffffff, 1);
    scene.add(ambientLight);

    camera.position.set(0, 1, 4); 
    animate();
}

function createObstacle(type, zPos) {
    const geometry = new THREE.BoxGeometry(0.6, 0.6, 0.6);
    let obsColor = 0xff0000; 
    if (type === 'ባጃጅ') obsColor = 0x0000ff; 
    if (type === 'ሌባ') obsColor = 0x00ff00; 

    const material = new THREE.MeshBasicMaterial({ color: obsColor });
    const obsMesh = new THREE.Mesh(geometry, material);
    
    const lanes = [-0.8, 0, 0.8];
    const randomLane = lanes[Math.floor(Math.random() * lanes.length)];
    
    obsMesh.position.set(randomLane, -0.7, zPos);
    obsMesh.userData = { type: type };
    scene.add(obsMesh);
    obstacles.push(obsMesh);
}

function animate() {
    if (isGameOver) return;
    
    animationFrameId = requestAnimationFrame(animate);
    
    if (activeGame === 'sheep' || activeGame === 'የበግ ሩጫ 3D') {
        obstacles.forEach((obs) => {
            obs.position.z += 0.08; 
            
            if (obs.position.z > 2) {
                obs.position.z = -20 - Math.random() * 10;
                const lanes = [-0.8, 0, 0.8];
                obs.position.x = lanes[Math.floor(Math.random() * lanes.length)];
                gameScore += 10;

                // የሽንፈት ወይም የማሸነፍ ወሰን (ለምሳሌ 50 ነጥብ ከደረሰ ያሸንፋል)
                if (gameScore >= 50) {
                    isGameOver = true;
                    alert(`እንኳን ደስ አለዎት! 50 ነጥብ ሞልተው በጉን በሰላም አሳረፉት!`);
                    sendGameResult(gameScore, 'win'); // ማሸነፉን ለባክኤንድ መላክ
                    exitGame();
                }
            }

            // ግጭት ሲፈጠር
            if (gameCube && Math.abs(obs.position.z - gameCube.position.z) < 0.5 && Math.abs(obs.position.x - gameCube.position.x) < 0.5) {
                isGameOver = true;
                alert(`ጌም ኦቨር! በጉ በ ${obs.userData.type} ተገጭቶ ገደል ገባ! ያገኙት ነጥብ: ${gameScore}`);
                sendGameResult(gameScore, 'lose'); // መሸነፉን ለባክኤንድ መላክ
                exitGame();
            }
        });
    } 
    else if (gameCube) {
        if (activeGame === 'mouse' || activeGame === 'የአይጥ ጨዋታ 3D') {
            gameCube.position.x = Math.sin(Date.now() * 0.005) * 1;
        } else if (activeGame === 'lion' || activeGame === 'የአንበሳ አደን 3D') {
            gameCube.position.y = Math.abs(Math.sin(Date.now() * 0.003)) * 1;
        }
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

// --- 3. ዘውድና ጎፈር ሎጂክ ---
async function triggerCoinFlip(choice) {
    const betAmount = parseFloat(document.getElementById("bet-amount").value || 0);
    if (betAmount <= 0) return alert("እባክዎ መጀመሪያ ትክክለኛ የብር መጠን ያስገቡ!");

    try {
        const res = await fetch('/api/coin_flip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, choice: choice, bet_amount: betAmount })
        });
        const data = await res.json();
        alert(data.message);
        fetchBalance();
    } catch (e) { alert("የሳንቲም ጨዋታው አልሰራም!"); }
}

window.addEventListener('resize', () => {
    if (camera && renderer) {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    }
});
