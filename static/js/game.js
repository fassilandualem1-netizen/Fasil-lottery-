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

// --- 2. 3D ጨዋታ ማስነሻ (ባላንስ ሳይኖር ለሙከራ የሚከፈት) ---
async function launchGame(gameType) {
    // ባላንስን ሳይጠብቅ ጨዋታውን በቀጥታ ይከፍታል
    activeGame = gameType;
    document.getElementById("game-canvas-container").style.display = "block";
    init3DWorld();
    
    // በሰርቨር በኩል የሆነ ችግር ካለ ለማወቅ ይህን ተጠቀም
    console.log("ጨዋታው በሙከራ ሁነታ ተከፍቷል:", gameType);
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

    // --- ቀላሉ መንገድ: ምስልን እንደ 3D በግ መጠቀም ---
    const textureLoader = new THREE.TextureLoader();
    // ይህ በግ ያለበት ምስል ሊንክ ነው
    const sheepTexture = textureLoader.load('https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Sheep_icon.svg/512px-Sheep_icon.svg.png');
    
    const material = new THREE.SpriteMaterial({ map: sheepTexture });
    gameCube = new THREE.Sprite(material);
    
    gameCube.scale.set(2, 2, 1); // የበጉ መጠን
    scene.add(gameCube);
    // ------------------------------------------

    const ambientLight = new THREE.AmbientLight(0xffffff, 1);
    scene.add(ambientLight);

    camera.position.set(0, 0, 3); // ካሜራውን ወደ በጉ አስጠጋነው
    animate();
}


        // በጉን መጫኛ
    const loader = new THREE.GLTFLoader();
    loader.load('/static/models/sheep.glb', (gltf) => {
        gameCube = gltf.scene; 
        
        // 1. በጉን መሃል ላይ ማድረግ እና መጠኑን ማስተካከል
        gameCube.position.set(0, 0, 0);
        gameCube.scale.set(1, 1, 1); // ትንሽ ከሆነ ቁጥሮቹን ወደ 2 ወይም 3 ማሳደግ ትችላለህ
        
        scene.add(gameCube);
        
        // 2. በጉ በትክክል ከተጫነ በስክሪኑ ላይ መልእክት እንዲያወጣ
        alert("በጉ በትክክል ተጭኗል!"); 
        
    }, undefined, (error) => {
        // 3. ስህተት ካለ ምን እንደሆነ በስክሪኑ ላይ እንዲያወጣ
        alert("ስህተት: ፋይሉ አልተገኘም ወይም አልተጫነም።");
        console.error("በጉን መጫን አልተቻለም:", error);
    });

    // 4. መብራቶች (በጉ እንዳይጨልም)
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
    directionalLight.position.set(5, 5, 5);
    scene.add(directionalLight);

    // 5. ካሜራው ትክክል በጉን እንዲያይ ማስተካከል
    camera.position.set(0, 2, 5);
    camera.lookAt(0, 0, 0);
    
    animate();
}

function animate() {
    animationFrameId = requestAnimationFrame(animate);
    // በጉን ማሽከርከር ካስፈለገህ ይህንን ተጠቀም
    if (gameCube) {
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
