const tg = window.Telegram.WebApp;
tg.expand();
const initData = tg.initData || "";
const userId = tg.initDataUnsafe?.user?.id || "999999";

// State Management
let selectedBets = {}; 
let allMatches = [];
let currentTab = 'top';     // 'top' ወይም 'upcoming'
let currentMarket = '1x2';  // '1x2' ወይም 'dc'

// ==========================================
// 1. Time Formatter (Flashscore Style)
// ==========================================
function formatLocalTime(apiDateStr, apiTimeStr) {
    try {
        let combinedDate = apiTimeStr ? `${apiDateStr}T${apiTimeStr}Z` : apiDateStr;
        const matchDate = new Date(combinedDate);
        if (isNaN(matchDate.getTime())) return { date: "TBA", time: "TBA" };

        const now = new Date();
        const hours = matchDate.getHours().toString().padStart(2, '0');
        const minutes = matchDate.getMinutes().toString().padStart(2, '0');
        const timeString = `${hours}:${minutes}`;

        let dateString = "";
        const isToday = matchDate.getDate() === now.getDate() && matchDate.getMonth() === now.getMonth() && matchDate.getFullYear() === now.getFullYear();
        
        const tomorrow = new Date(now);
        tomorrow.setDate(tomorrow.getDate() + 1);
        const isTomorrow = matchDate.getDate() === tomorrow.getDate() && matchDate.getMonth() === tomorrow.getMonth() && matchDate.getFullYear() === tomorrow.getFullYear();

        if (isToday) dateString = "ዛሬ";
        else if (isTomorrow) dateString = "ነገ";
        else dateString = `${matchDate.getDate().toString().padStart(2, '0')}/${(matchDate.getMonth() + 1).toString().padStart(2, '0')}`;

        return { date: dateString, time: timeString };
    } catch (e) {
        return { date: "TBA", time: "TBA" };
    }
}

// ==========================================
// 2. Tabs & Markets Switchers
// ==========================================
function switchTab(tab) {
    currentTab = tab;
    // የ UI በተኖችን አክቲቭ ስቴት እዚህ ጋር መቀየር ትችላለህ (በ CSS)
    fetchMatches();
}

function switchMarket(market) {
    currentMarket = market;
    // የ UI በተኖችን አክቲቭ ስቴት እዚህ ጋር መቀየር ትችላለህ (በ CSS)
    renderMatches(); 
}

// ==========================================
// 3. Fetch Matches (ከ API)
// ==========================================
async function fetchMatches() {
    const list = document.getElementById("matches-list");
    list.innerHTML = "<p class='text-center text-gray-500 mt-10'>ጨዋታዎችን በማምጣት ላይ... ⏳</p>";

    try {
        const res = await fetch(`/api/sports/odds?tab=${currentTab}`); 
        const data = await res.json();
        
        if (!data.matches || data.matches.length === 0) {
            list.innerHTML = "<p class='text-center text-gray-500 mt-10'>ለአሁኑ ምንም ጨዋታ የለም!</p>";
            return;
        }

        allMatches = data.matches;
        renderMatches();

    } catch (e) {
        console.error(e);
        list.innerHTML = "<p class='text-center text-red-500 mt-10'>ስህተት ተፈጥሯል! ኢንተርኔትዎን ያረጋግጡ።</p>";
    }
}

// ==========================================
// 4. Render Matches (ወደ HTML)
// ==========================================
function renderMatches() {
    const list = document.getElementById("matches-list");
    list.innerHTML = "";

    allMatches.forEach(m => {
        const mid = m.fixture.id; 
        const home = m.fixture.teams.home.name; 
        const away = m.fixture.teams.away.name; 
        const odds = m.odds || {};
        const league = m.fixture.league || "Unknown";

        const safeHome = home.replace(/'/g, "\\'");
        const safeAway = away.replace(/'/g, "\\'");
        const matchTitle = `${safeHome} V ${safeAway}`;

        const timeInfo = formatLocalTime(m.fixture.date, m.fixture.time);

        let buttonsHTML = "";

        if (currentMarket === '1x2') {
            const drawBtn = odds.draw ? `
                <button id="btn-${mid}-draw" onclick="selectOdd('${mid}', 'draw', ${odds.draw}, '${matchTitle}', 'Draw')" class="bg-gray-900 border border-gray-800 py-2 rounded-lg flex flex-col items-center hover:border-yellow-500 transition">
                    <span class="text-[9px] text-gray-400">X</span><span class="text-yellow-400 font-bold text-xs">${odds.draw}</span>
                </button>
            ` : `<div class="bg-gray-900/50 border border-gray-800 py-2 rounded-lg flex flex-col items-center justify-center opacity-50"><span class="text-[9px] text-gray-500">-</span></div>`;

            buttonsHTML = `
                <button id="btn-${mid}-home" onclick="selectOdd('${mid}', 'home', ${odds.home}, '${matchTitle}', '${safeHome}')" class="bg-gray-900 border border-gray-800 py-2 rounded-lg flex flex-col items-center hover:border-yellow-500 transition">
                    <span class="text-[9px] text-gray-400">1</span><span class="text-yellow-400 font-bold text-xs">${odds.home}</span>
                </button>
                ${drawBtn}
                <button id="btn-${mid}-away" onclick="selectOdd('${mid}', 'away', ${odds.away}, '${matchTitle}', '${safeAway}')" class="bg-gray-900 border border-gray-800 py-2 rounded-lg flex flex-col items-center hover:border-yellow-500 transition">
                    <span class="text-[9px] text-gray-400">2</span><span class="text-yellow-400 font-bold text-xs">${odds.away}</span>
                </button>
            `;
        } else if (currentMarket === 'dc') {
            buttonsHTML = `
                <button id="btn-${mid}-1x" onclick="selectOdd('${mid}', '1x', ${odds.dc_1x}, '${matchTitle}', '1X')" class="bg-gray-900 border border-gray-800 py-2 rounded-lg flex flex-col items-center hover:border-yellow-500 transition">
                    <span class="text-[9px] text-gray-400">1X</span><span class="text-yellow-400 font-bold text-xs">${odds.dc_1x}</span>
                </button>
                <button id="btn-${mid}-12" onclick="selectOdd('${mid}', '12', ${odds.dc_12}, '${matchTitle}', '12')" class="bg-gray-900 border border-gray-800 py-2 rounded-lg flex flex-col items-center hover:border-yellow-500 transition">
                    <span class="text-[9px] text-gray-400">12</span><span class="text-yellow-400 font-bold text-xs">${odds.dc_12}</span>
                </button>
                <button id="btn-${mid}-x2" onclick="selectOdd('${mid}', 'x2', ${odds.dc_x2}, '${matchTitle}', 'X2')" class="bg-gray-900 border border-gray-800 py-2 rounded-lg flex flex-col items-center hover:border-yellow-500 transition">
                    <span class="text-[9px] text-gray-400">X2</span><span class="text-yellow-400 font-bold text-xs">${odds.dc_x2}</span>
                </button>
            `;
        }

        list.innerHTML += `
        <div class="bg-slate-950 p-4 rounded-xl border border-gray-800 shadow-lg mb-3">
            <div class="flex justify-between items-center mb-2">
                <span class="text-[10px] text-gray-400 uppercase">⚽ ${league}</span>
                <span class="text-[10px] text-gray-400">${timeInfo.date} ${timeInfo.time}</span>
            </div>
            <div class="text-[11px] text-white font-bold mb-3 uppercase">${home} V ${away}</div>
            <div class="grid grid-cols-3 gap-2">
                ${buttonsHTML}
            </div>
        </div>`;
    });

    restoreSelections();
}

// ==========================================
// 5. Select Odd & Update UI
// ==========================================
function selectOdd(mid, pick, odd, matchName, teamName) {
    const btnId = `btn-${mid}-${pick}`;
    const btn = document.getElementById(btnId);

    if (selectedBets[mid] && selectedBets[mid].pick === pick) {
        delete selectedBets[mid];
        if(btn) btn.className = "bg-gray-900 border border-gray-800 py-2 rounded-lg flex flex-col items-center hover:border-yellow-500 transition";
    } else {
        if (selectedBets[mid]) {
            const oldBtn = document.getElementById(`btn-${mid}-${selectedBets[mid].pick}`);
            if(oldBtn) oldBtn.className = "bg-gray-900 border border-gray-800 py-2 rounded-lg flex flex-col items-center hover:border-yellow-500 transition";
        }
        
        selectedBets[mid] = { matchId: mid, pick: pick, odd: odd, matchName: matchName, team: teamName };
        if(btn) btn.className = "bg-yellow-600 border border-yellow-500 py-2 rounded-lg flex flex-col items-center transition";
    }
    updateBetSlip();
}

function restoreSelections() {
    for (const mid in selectedBets) {
        const btn = document.getElementById(`btn-${mid}-${selectedBets[mid].pick}`);
        if (btn) btn.className = "bg-yellow-600 border border-yellow-500 py-2 rounded-lg flex flex-col items-center transition";
    }
}

// ==========================================
// 6. Update Bet Slip & Bonus Math
// ==========================================
function updateBetSlip() {
    let count = Object.keys(selectedBets).length;
    let totalOdds = 1.0;
    
    for (let id in selectedBets) totalOdds *= selectedBets[id].odd;
    if (count === 0) totalOdds = 0;

    let bonusPercent = (count >= 3) ? 5 : 0; 
    
    document.getElementById("slip-count").innerText = count;
    document.getElementById("slip-odds").innerText = totalOdds.toFixed(2);
    
    const amountInput = document.getElementById("bet-amount");
    const amount = amountInput ? parseFloat(amountInput.value || 0) : 0;
    
    const rawWin = amount * totalOdds;
    const bonusAmount = rawWin * (bonusPercent / 100);
    const finalWin = rawWin + bonusAmount;

    const winDisplay = document.getElementById("possible-win");
    if(winDisplay) winDisplay.innerText = finalWin.toFixed(2);
    
    const slipContainer = document.getElementById("bet-slip-container");
    if(slipContainer) slipContainer.style.display = count > 0 ? "block" : "none";
}

// ==========================================
// 7. Place Bet API
// ==========================================
async function placeBet() {
    const amountInput = document.getElementById("bet-amount");
    const amount = amountInput ? parseFloat(amountInput.value || 0) : 0;
    const selections = Object.values(selectedBets);
    
    if (selections.length === 0) return alert("እባክዎ ቢያንስ አንድ ጨዋታ ይምረጡ!");
    if (amount < 10) return alert("እባክዎ ቢያንስ 10 ብር ያስገቡ!");

    const btn = document.querySelector("button[onclick='placeBet()']");
    const originalText = btn.innerText;
    btn.innerText = "በመላክ ላይ... ⏳";
    btn.disabled = true;

    try {
        const res = await fetch('/api/sports/place_bet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': initData },
            body: JSON.stringify({ user_id: userId, bet_amount: amount, selections: selections })
        });
        const data = await res.json();
        
        alert(data.message);
        if(data.status === "success") window.location.reload(); 
        else { btn.innerText = originalText; btn.disabled = false; }
    } catch (e) {
        alert("ከሰርቨር ጋር መገናኘት አልተቻለም!");
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

// ==========================================
// 8. My Bets (ቲኬት መመልከቻ)
// ==========================================
async function showMyBets() {
    // ሜይን ፔጅ ደብቆ ቲኬት ፔጅ ማሳያ
    document.getElementById("matches-list").style.display = "none";
    document.getElementById("my-bets-container").style.display = "block";
    
    const ticketsList = document.getElementById("tickets-list");
    ticketsList.innerHTML = "<p class='text-center text-gray-500 mt-10'>ቲኬቶችን በማምጣት ላይ... ⏳</p>";

    try {
        const res = await fetch(`/api/sports/my_bets?user_id=${userId}`);
        const data = await res.json();

        if (data.status === "success" && data.tickets.length > 0) {
            ticketsList.innerHTML = "";
            data.tickets.reverse().forEach(ticket => {
                let statusIcon = "⏳"; let statusColor = "text-gray-400"; let borderColor = "border-gray-600";
                if (ticket.status === "won") { statusIcon = "✅"; statusColor = "text-green-500"; borderColor = "border-green-500"; }
                if (ticket.status === "lost") { statusIcon = "❌"; statusColor = "text-red-500"; borderColor = "border-red-500"; }

                let html = `
                    <div class="bg-slate-900 p-4 mb-3 rounded-lg border-l-4 ${borderColor} shadow-md">
                        <div class="flex justify-between font-bold mb-2 text-xs">
                            <span class="text-gray-300">ID: ${ticket.ticket_id}</span>
                            <span class="${statusColor}">${statusIcon} ${ticket.status.toUpperCase()}</span>
                        </div>
                        <div class="text-[11px] text-gray-400 mb-2">
                            Stake: <b class="text-white">${ticket.amount} ETB</b> | Odds: <b class="text-white">${ticket.total_odds.toFixed(2)}</b><br>
                            Possible Win: <b class="text-yellow-400">${ticket.possible_win.toFixed(2)} ETB</b>
                        </div>
                        <hr class="border-gray-800 my-2">
                        <ul class="text-[10px] text-gray-300">
                `;

                ticket.selections.forEach(sel => {
                    let mStatus = "⏳";
                    if (sel.status === "won") mStatus = "👍";
                    if (sel.status === "lost") mStatus = "👎";
                    html += `<li class="mb-1">${mStatus} <b>${sel.team}</b> (${sel.pick.toUpperCase()}) @ ${sel.odd}</li>`;
                });

                html += `</ul></div>`;
                ticketsList.innerHTML += html;
            });
        } else {
            ticketsList.innerHTML = "<p class='text-center text-gray-500 mt-10'>ምንም የተቆረጠ ቲኬት የለም።</p>";
        }
    } catch (error) {
        ticketsList.innerHTML = "<p class='text-center text-red-500 mt-10'>ስህተት ተፈጥሯል!</p>";
    }
}

function closeMyBets() {
    document.getElementById("my-bets-container").style.display = "none";
    document.getElementById("matches-list").style.display = "block";
}

// ፔጁ ሲከፈት ጀምር
fetchMatches();
