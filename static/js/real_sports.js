const tg = window.Telegram.WebApp;
tg.expand();
const initData = tg.initData || "";
const userData = tg.initDataUnsafe?.user || { id: "8488592165" };

let selectedBets = {}; // { match_id: { pick: 'home', odd: 1.8 } }

// 1. ጨዋታዎችን ማምጣት
async function fetchMatches() {
    try {
        const res = await fetch('/api/sports/matches');
        const data = await res.json();
        
        const list = document.getElementById("matches-list");
        list.innerHTML = "";

        if (data.matches.length === 0) {
            list.innerHTML = "<p style='text-align:center;'>ለአሁኑ ምንም ጨዋታ የለም!</p>";
            return;
        }

        data.matches.forEach(m => {
            const matchId = m.fixture.id;
            const home = m.teams.home.name;
            const away = m.teams.away.name;
            const odds = m.odds; // {home: 1.8, draw: 3.2, away: 4.1}

            list.innerHTML += `
                <div class="match-card">
                    <div class="teams"><span>🏠 ${home}</span> <span>vs</span> <span>✈️ ${away}</span></div>
                    <div class="odds-container">
                        <button class="odd-btn" id="btn-${matchId}-home" onclick="selectOdd(${matchId}, '${home}', 'home', ${odds.home})">1 <br> ${odds.home}</button>
                        <button class="odd-btn" id="btn-${matchId}-draw" onclick="selectOdd(${matchId}, 'Draw', 'draw', ${odds.draw})">X <br> ${odds.draw}</button>
                        <button class="odd-btn" id="btn-${matchId}-away" onclick="selectOdd(${matchId}, '${away}', 'away', ${odds.away})">2 <br> ${odds.away}</button>
                    </div>
                </div>
            `;
        });
    } catch (e) {
        document.getElementById("matches-list").innerHTML = "<p>ስህተት ተፈጥሯል።</p>";
    }
}

// 2. ኦድ ሲመረጥ (Button Click)
function selectOdd(matchId, teamName, pickType, oddValue) {
    // የቀድሞ ምርጫ ካለ Button ከለሩን እናጠፋለን
    if (selectedBets[matchId]) {
        document.getElementById(`btn-${matchId}-${selectedBets[matchId].pickType}`).classList.remove("selected");
    }

    // አዲስ ምርጫ ከሆነ እንጨምረዋለን (እንደገና ከነካው እንዲያጠፋው 토글)
    if (selectedBets[matchId] && selectedBets[matchId].pickType === pickType) {
        delete selectedBets[matchId];
    } else {
        selectedBets[matchId] = { pickType: pickType, odd: oddValue, matchId: matchId };
        document.getElementById(`btn-${matchId}-${pickType}`).classList.add("selected");
    }
    
    updateBetSlip();
}

// 3. Bet Slip ማሳያውን ማስተካከል
function updateBetSlip() {
    let count = 0;
    let totalOdds = 1.0;
    
    for (let id in selectedBets) {
        count++;
        totalOdds *= selectedBets[id].odd;
    }
    
    if (count === 0) totalOdds = 1.0;

    document.getElementById("slip-count").innerText = count;
    document.getElementById("slip-odds").innerText = totalOdds.toFixed(2);
    
    const amount = parseFloat(document.getElementById("bet-amount").value || 0);
    document.getElementById("possible-win").innerText = (amount * totalOdds).toFixed(2);
}

// 4. ውርርድ መላክ (Place Bet)
async function placeBet() {
    const amount = parseFloat(document.getElementById("bet-amount").value || 0);
    const selections = Object.values(selectedBets);
    
    if (selections.length === 0) return alert("እባክዎ ቢያንስ አንድ ጨዋታ ይምረጡ!");
    if (amount <= 0) return alert("እባክዎ የብር መጠን ያስገቡ!");

    try {
        const res = await fetch('/api/sports/place_bet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': initData },
            body: JSON.stringify({ user_id: userData.id, bet_amount: amount, selections: selections })
        });
        const data = await res.json();
        
        alert(data.message);
        
        if(data.status === "success") {
            // ስኬታማ ከሆነ ፔጁን Reset እናደርጋለን
            selectedBets = {};
            document.querySelectorAll('.odd-btn').forEach(b => b.classList.remove('selected'));
            document.getElementById("bet-amount").value = "";
            updateBetSlip();
        }
    } catch (e) {
        alert("ከሰርቨር ጋር መገናኘት አልተቻለም!");
    }
}

// ገጹ ሲከፈት ጨዋታዎቹን አምጣ
fetchMatches();
