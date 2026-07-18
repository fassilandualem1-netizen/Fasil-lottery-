const tg = window.Telegram.WebApp;
tg.expand();
const initData = tg.initData || "";
const userId = tg.initDataUnsafe?.user?.id || "999999";

let selectedBets = {}; 

// 1. ጨዋታዎችን ማምጣት
async function fetchMatches() {
    try {
        const res = await fetch('/api/sports/matches');
        const data = await res.json();
        const list = document.getElementById("matches-list");
        list.innerHTML = "";

        if (!data.matches || data.matches.length === 0) {
            list.innerHTML = "<p class='text-center text-gray-500'>ለአሁኑ ምንም ጨዋታ የለም!</p>";
            return;
        }

        data.matches.forEach(m => {
            const mid = m.fixture.id;
            const home = m.teams.home.name;
            const away = m.teams.away.name;
            const odds = m.odds;

            list.innerHTML += `
            <div class="bg-slate-950 p-4 rounded-xl border border-gray-800 shadow-lg">
                <div class="text-[10px] text-gray-500 font-bold mb-2 uppercase">⚽ ${home} V ${away}</div>
                <div class="grid grid-cols-3 gap-2">
                    <button id="btn-${mid}-home" onclick="selectOdd(${mid}, 'home', ${odds.home}, '${home}')" class="bg-gray-900 border border-gray-800 py-2 rounded-lg flex flex-col items-center hover:border-yellow-500 transition">
                        <span class="text-[9px] text-gray-400">1</span><span class="text-yellow-400 font-bold text-xs">${odds.home}</span>
                    </button>
                    <button id="btn-${mid}-draw" onclick="selectOdd(${mid}, 'draw', ${odds.draw}, 'Draw')" class="bg-gray-900 border border-gray-800 py-2 rounded-lg flex flex-col items-center hover:border-yellow-500 transition">
                        <span class="text-[9px] text-gray-400">X</span><span class="text-yellow-400 font-bold text-xs">${odds.draw}</span>
                    </button>
                    <button id="btn-${mid}-away" onclick="selectOdd(${mid}, 'away', ${odds.away}, '${away}')" class="bg-gray-900 border border-gray-800 py-2 rounded-lg flex flex-col items-center hover:border-yellow-500 transition">
                        <span class="text-[9px] text-gray-400">2</span><span class="text-yellow-400 font-bold text-xs">${odds.away}</span>
                    </button>
                </div>
            </div>`;
        });
    } catch (e) {
        console.error(e);
        document.getElementById("matches-list").innerHTML = "<p class='text-center text-red-500'>ስህተት ተፈጥሯል!</p>";
    }
}

// 2. ኦድ (Odd) ሲመረጥ ከለር መቀየር
function selectOdd(mid, pick, odd, teamName) {
    const btnId = `btn-${mid}-${pick}`;
    const btn = document.getElementById(btnId);

    // ምርጫውን መቀያየር (Toggle)
    if (selectedBets[mid] && selectedBets[mid].pick === pick) {
        delete selectedBets[mid];
        btn.className = "bg-gray-900 border border-gray-800 py-2 rounded-lg flex flex-col items-center hover:border-yellow-500 transition";
    } else {
        // የቀድሞ ምርጫ ካለ እናጠፋለን
        if (selectedBets[mid]) {
            const oldPick = selectedBets[mid].pick;
            document.getElementById(`btn-${mid}-${oldPick}`).className = "bg-gray-900 border border-gray-800 py-2 rounded-lg flex flex-col items-center hover:border-yellow-500 transition";
        }
        
        selectedBets[mid] = { matchId: mid, pick: pick, odd: odd, team: teamName };
        btn.className = "bg-yellow-600 border border-yellow-500 py-2 rounded-lg flex flex-col items-center transition";
    }
    updateBetSlip();
}

// 3. Bet Slip ማስተካከል
function updateBetSlip() {
    let count = Object.keys(selectedBets).length;
    let totalOdds = 1.0;
    
    for (let id in selectedBets) totalOdds *= selectedBets[id].odd;
    
    document.getElementById("slip-count").innerText = count;
    document.getElementById("slip-odds").innerText = totalOdds.toFixed(2);
    
    const amount = parseFloat(document.getElementById("bet-amount").value || 0);
    document.getElementById("possible-win").innerText = (amount * totalOdds).toFixed(2);
    
    // በ CSS በኩል ለማሳየት
    document.getElementById("bet-slip-container").style.display = count > 0 ? "block" : "none";
}

// 4. ውርርድ መላክ
async function placeBet() {
    const amount = parseFloat(document.getElementById("bet-amount").value || 0);
    const selections = Object.values(selectedBets);
    
    if (selections.length === 0) return alert("እባክዎ ቢያንስ አንድ ጨዋታ ይምረጡ!");
    if (amount <= 0) return alert("እባክዎ የብር መጠን ያስገቡ!");

    try {
        const res = await fetch('/api/sports/place_bet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': initData },
            body: JSON.stringify({ user_id: userId, bet_amount: amount, selections: selections })
        });
        const data = await res.json();
        
        alert(data.message);
        
        if(data.status === "success") {
            window.location.reload(); // ስኬታማ ከሆነ ገጹን ሪፍሬሽ ማድረግ
        }
    } catch (e) {
        alert("ከሰርቨር ጋር መገናኘት አልተቻለም!");
    }
}

fetchMatches();
