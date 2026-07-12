// --- 1. የቴሌግራም መነሻ ---
const tg = window.Telegram.WebApp;
tg.expand();
const userData = tg.initDataUnsafe?.user || { id: "8488592165", first_name: "የሰፈር ልጅ" };
const userId = userData.id.toString();

let activeGame = null;
let scene, camera, renderer, gameCube, animationFrameId;

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("user-name").innerText = userData.first_name;
});

// --- 2. 3D ጨዋታ ማስነሻ ---
async function launchGame(gameType) {
    activeGame = gameType;
    document.getElementById("game-canvas-container").style.display = "block";
    init3DWorld();
}

// 3D አለም መፍጠሪያ (የተስተካከለ)
function init3DWorld() {
    const container = document.getElementById("game-canvas-container");

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x87CEEB); 

    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    container.appendChild(renderer.domElement);

    // በጉን እንደ ምስል መጫን (ቀላሉ መንገድ)
    const textureLoader = new THREE.TextureLoader();
    const sheepTexture = textureLoader.load('https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Sheep_icon.svg/512px-Sheep_icon.svg.png');
    const material = new THREE.SpriteMaterial({ map: sheepTexture });
    gameCube = new THREE.Sprite(material);
    gameCube.scale.set(2, 2, 1); 
    scene.add(gameCube);

    const ambientLight = new THREE.AmbientLight(0xffffff, 1);
    scene.add(ambientLight);

    camera.position.set(0, 0, 3);
    animate();
}

function animate() {
    animationFrameId = requestAnimationFrame(animate);
    if (gameCube) {
        // በጉ እንዲንቀሳቀስ (ለሩጫ ጨዋታ)
        gameCube.position.z += 0.02;
        if (gameCube.position.z > 2) gameCube.position.z = -2;
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
}
