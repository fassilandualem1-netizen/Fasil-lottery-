// --- 1. የቴሌግራም መነሻ ---
const tg = window.Telegram.WebApp;
tg.expand();

const userData = tg.initDataUnsafe?.user || { id: "8488592165", first_name: "የሰፈር ልጅ" };
const userId = userData.id.toString();

let currentBalance = 0;
let activeGame = null;
let scene, camera, renderer, gameCube, animationFrameId;

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("user-name").innerText = userData.first_name;
    fetchBalance();
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

// --- 2. 3D ጨዋታ ማስነሻ ---
async function launchGame(gameType) {
    try {
        const res = await fetch('/api/start_game', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, game_type: gameType })
        });
        const data = await res.json();

        if (data.status === "ready") {
            fetchBalance();
            activeGame = gameType;
            document.getElementById("game-canvas-container").style.display = "block";
            init3DWorld();
        } else {
            alert(data.message || "በቂ ባላንስ የሎትም!");
        }
    } catch (e) { alert("የሰርቨር ስህተት ተከስቷል!"); }
}

// Three.js አለም መፍጠሪያ (ስህተቱ የተስተካከለበት)
function init3DWorld() {
    const container = document.getElementById("game-canvas-container");
    
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a1a);

    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    container.appendChild(renderer.domElement);

    const geometry = new THREE.BoxGeometry(2, 2, 2);
    // እዚህ ጋ የነበረው MeshMesh ስህተት ተስተካክሏል
    const material = new THREE.MeshStandardMaterial({ color: 0x00ff88, roughness: 0.4 });
    gameCube = new THREE.Mesh(geometry, material);
    scene.add(gameCube);

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 10, 7);
    scene.add(directionalLight);

    camera.position.z = 5;
    animate();
}

function animate() {
    animationFrameId = requestAnimationFrame(animate);
    if (gameCube) {
        gameCube.rotation.x += 0.01;
        gameCube.rotation.y += 0.01;
    }
    renderer.render(scene, camera);
}

function exitGame() {
    cancelAnimationFrame(animationFrameId);
    activeGame = null;
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
