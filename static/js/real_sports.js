const tg = window.Telegram?.WebApp;
if (tg) {
    try {
        tg.expand();
        tg.ready();
    } catch (e) {}
}

const initData = tg?.initData || "";
const userId = tg?.initDataUnsafe?.user?.id ? String(tg.initDataUnsafe.user.id) : "999999";

let allMatches = [];
let selectedBets = {};
let currentTab = "football";
let currentMarket = "1x2";
let searchTerm = "";
let favoritesOnly = false;
let favorites = JSON.parse(localStorage.getItem("sports_favorites") || "[]");

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function setTabUI() {
    document.getElementById("tab-football").classList.add("active");
}

function setMarketUI() {
    document.getElementById("market-1x2").classList.toggle("active", currentMarket === "1x2");
    document.getElementById("market-dc").classList.toggle("active", currentMarket === "dc");
}

function setStake(amount) {
    const input = document.getElementById("bet-amount");
    if (input) {
        input.value = amount;
        updateBetSlip();
    }
}

function switchTab(tab) {
    currentTab = tab;
    setTabUI();
    fetchMatches();
}

function switchMarket(market) {
    currentMarket = market;
    setMarketUI();
    renderMatches();
    renderHotPicks();
}

function toggleFavorite(matchId) {
    if (favorites.includes(matchId)) {
        favorites = favorites.filter(x => x !== matchId);
    } else {
        favorites.push(matchId);
    }

    localStorage.setItem("sports_favorites", JSON.stringify(favorites));
    renderMatches();
    renderHotPicks();
}

function getFilteredMatches() {
    let filtered = [...allMatches];

    if (favoritesOnly) {
        filtered = filtered.filter(match => favorites.includes(match.fixture?.id));
    }

    if (searchTerm) {
        const q = searchTerm.toLowerCase();
        filtered = filtered.filter(match => {
            const home = (match.fixture?.teams?.home?.name || "").toLowerCase();
            const away = (match.fixture?.teams?.away?.name || "").toLowerCase();
            const league = (match.fixture?.league || "").toLowerCase();
            return home.includes(q) || away.includes(q) || league.includes(q);
        });
    }

    return filtered;
}

function formatLocalTime(apiDateStr, apiTimeStr) {
    if (!apiDateStr || apiDateStr === "TBA") {
        return { date: "TBA", time: apiTimeStr || "TBA" };
    }

    try {
        const matchDate = new Date(apiDateStr);
        const today = new Date();

        const isToday =
            matchDate.getDate() === today.getDate() &&
            matchDate.getMonth() === today.getMonth() &&
            matchDate.getFullYear() === today.getFullYear();

        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);

        const isTomorrow =
            matchDate.getDate() === tomorrow.getDate() &&
            matchDate.getMonth() === tomorrow.getMonth() &&
            matchDate.getFullYear() === tomorrow.getFullYear();

        let dateText = "";
        if (isToday) dateText = "Today";
        else if (isTomorrow) dateText = "Tomorrow";
        else {
            dateText = `${String(matchDate.getDate()).padStart(2, "0")}/${String(matchDate.getMonth() + 1).padStart(2, "0")}`;
        }

        return { date: dateText, time: apiTimeStr || "TBA" };
    } catch (e) {
        return { date: "TBA", time: apiTimeStr || "TBA" };
    }
}

async function fetchBalance() {
    try {
        const headers = {};
        if (initData) headers["X-Telegram-Init-Data"] = initData;

        const res = await fetch("/api/wallet/balance", { headers });
        const data = await res.json();
        const wallet = document.getElementById("wallet-balance");
        if (wallet) {
            wallet.innerText = `${Number(data.balance || 0).toFixed(2)} ETB`;
        }
    } catch (e) {
        console.error(e);
    }
}

async function fetchMatches() {
    const list = document.getElementById("matches-list");
    list.innerHTML = "<div class='loading-text'>Loading football matches...</div>";

    try {
        const res = await fetch(`/api/sports/odds?tab=${currentTab}`);
        const data = await res.json();

        if (!data.matches || data.matches.length === 0) {
            list.innerHTML = "<div class='loading-text'>No football matches available right now.</div>";
            return;
        }

        allMatches = data.matches;
        renderMatches();
        renderHotPicks();
    } catch (e) {
        console.error(e);
        list.innerHTML = "<div class='loading-text'>Could not load football matches.</div>";
    }
}

function createOddButton(matchId, pick, odd, label, matchTitle, teamName) {
    const selected = selectedBets[matchId] && selectedBets[matchId].pick === pick;
    const selectedClass = selected ? "odd-btn selected" : "odd-btn";
    const safeTitle = escapeHtml(matchTitle);
    const safeTeam = escapeHtml(teamName);

    return `
        <button class="${selectedClass}" onclick="selectOdd('${matchId}', '${pick}', ${odd}, '${safeTitle}', '${safeTeam}')">
            <span>${label}</span>
            <span>${Number(odd).toFixed(2)}</span>
        </button>
    `;
}

function renderMatches() {
    const list = document.getElementById("matches-list");
    list.innerHTML = "";

    const filtered = getFilteredMatches();
    if (filtered.length === 0) {
        list.innerHTML = "<div class='loading-text'>No football matches match your search.</div>";
        return;
    }

    filtered.forEach(match => {
        const mid = match.fixture?.id || Math.random().toString(36).slice(2);
        const home = match.fixture?.teams?.home?.name || "Home";
        const away = match.fixture?.teams?.away?.name || "Away";
        const league = match.fixture?.league || "Football League";
        const odds = match.odds || {};
        const timeInfo = formatLocalTime(match.fixture?.date, match.fixture?.time);
        const matchTitle = `${home} vs ${away}`;
        const isFavorite = favorites.includes(mid);

        let oddsHtml = "";
        if (currentMarket === "1x2") {
            oddsHtml = `
                <div class="odds-grid">
                    ${createOddButton(mid, "home", odds.home || 0, "1", matchTitle, home)}
                    ${createOddButton(mid, "draw", odds.draw || 0, "X", matchTitle, "Draw")}
                    ${createOddButton(mid, "away", odds.away || 0, "2", matchTitle, away)}
                </div>
            `;
        } else {
            oddsHtml = `
                <div class="odds-grid">
                    ${createOddButton(mid, "1x", odds.dc_1x || 0, "1X", matchTitle, "1X")}
                    ${createOddButton(mid, "12", odds.dc_12 || 0, "12", matchTitle, "12")}
                    ${createOddButton(mid, "x2", odds.dc_x2 || 0, "X2", matchTitle, "X2")}
                </div>
            `;
        }

        const card = document.createElement("div");
        card.className = "match-card";
        card.innerHTML = `
            <div class="match-head">
                <span>⚽️ ${league}</span>
                <span>${timeInfo.date} ${timeInfo.time}</span>
            </div>
            <div class="match-actions">
                <div class="match-title">${home} v ${away}</div>
                <button class="favorite-btn" onclick="toggleFavorite('${mid}')">${isFavorite ? "★" : "☆"}</button>
            </div>
            ${oddsHtml}
        `;
        list.appendChild(card);
    });
}

function selectOdd(matchId, pick, odd, matchName, teamName) {
    if (selectedBets[matchId] && selectedBets[matchId].pick === pick) {
        delete selectedBets[matchId];
    } else {
        selectedBets[matchId] = { matchId, pick, odd, matchName, team: teamName };
    }

    renderMatches();
    updateBetSlip();
}

function updateBetSlip() {
    const count = Object.keys(selectedBets).length;
    const slipContainer = document.getElementById("bet-slip-container");
    const slipItems = document.getElementById("slip-items");

    if (count === 0) {
        slipContainer.style.display = "none";
        slipItems.innerHTML = "";
        document.getElementById("slip-count").innerText = "0";
        document.getElementById("slip-odds").innerText = "0.00";
        document.getElementById("possible-win").innerText = "0.00";
        return;
    }

    slipContainer.style.display = "flex";
    slipItems.innerHTML = "";

    let totalOdds = 1.0;
    Object.values(selectedBets).forEach(item => {
        totalOdds *= Number(item.odd || 1);
        const el = document.createElement("div");
        el.className = "slip-item";
        el.innerText = `${item.matchName} — ${item.team} (${item.pick.toUpperCase()}) @ ${Number(item.odd).toFixed(2)}`;
        slipItems.appendChild(el);
    });

    const amount = Number(document.getElementById("bet-amount").value || 0);
    const possibleWin = amount * totalOdds;

    document.getElementById("slip-count").innerText = count;
    document.getElementById("slip-odds").innerText = totalOdds.toFixed(2);
    document.getElementById("possible-win").innerText = possibleWin.toFixed(2);
}

function clearSelections() {
    selectedBets = {};
    renderMatches();
    updateBetSlip();
}

function renderHotPicks() {
    const container = document.getElementById("hot-picks");
    const filtered = getFilteredMatches();
    if (filtered.length === 0) {
        container.innerHTML = "";
        return;
    }

    const picks = [];
    filtered.forEach(match => {
        const odds = match.odds || {};
        const mid = match.fixture?.id || Math.random().toString(36).slice(2);
        const home = match.fixture?.teams?.home?.name || "Home";
        const away = match.fixture?.teams?.away?.name || "Away";
        const matchTitle = `${home} vs ${away}`;

        if (currentMarket === "1x2") {
            if (odds.home) picks.push({ title: `${home} to win`, desc: matchTitle, odd: odds.home });
            if (odds.draw) picks.push({ title: "Draw", desc: matchTitle, odd: odds.draw });
            if (odds.away) picks.push({ title: `${away} to win`, desc: matchTitle, odd: odds.away });
        } else {
            if (odds.dc_1x) picks.push({ title: "1X", desc: matchTitle, odd: odds.dc_1x });
            if (odds.dc_12) picks.push({ title: "12", desc: matchTitle, odd: odds.dc_12 });
            if (odds.dc_x2) picks.push({ title: "X2", desc: matchTitle, odd: odds.dc_x2 });
        }
    });

    picks.sort((a, b) => Number(b.odd) - Number(a.odd));
    const top = picks.slice(0, 3);

    if (top.length === 0) {
        container.innerHTML = "";
        return;
    }

    container.innerHTML = top.map(pick => `
        <div class="hot-card">
            <div class="hot-title">Hot Pick</div>
            <div class="hot-body">
                <span>${pick.title} • ${pick.desc}</span>
                <span class="pill">${Number(pick.odd).toFixed(2)}</span>
            </div>
        </div>
    `).join("");
}

async function placeBet() {
    const selections = Object.values(selectedBets);
    const amount = Number(document.getElementById("bet-amount").value || 0);

    if (selections.length === 0) {
        alert("Please select at least one football pick.");
        return;
    }

    if (amount < 10) {
        alert("Minimum bet is 10 ETB.");
        return;
    }

    const button = document.getElementById("place-bet-btn");
    const oldText = button.innerText;
    button.disabled = true;
    button.innerText = "Placing...";

    try {
        const headers = { "Content-Type": "application/json" };
        if (initData) headers["X-Telegram-Init-Data"] = initData;

        const res = await fetch("/api/sports/place_bet", {
            method: "POST",
            headers,
            body: JSON.stringify({
                user_id: userId,
                bet_amount: amount,
                selections: selections.map(item => ({
                    match_id: item.matchId,
                    pick: item.pick,
                    odd: item.odd,
                    team: item.team,
                    match_name: item.matchName
                }))
            })
        });

        const data = await res.json();
        alert(data.message || "Bet placed");
        if (data.status === "success") {
            await fetchBalance();
            clearSelections();
        }
    } catch (e) {
        console.error(e);
        alert("Could not place bet.");
    } finally {
        button.disabled = false;
        button.innerText = oldText;
    }
}

async function showMyBets() {
    document.getElementById("matches-list").style.display = "none";
    document.getElementById("hot-picks").style.display = "none";
    document.getElementById("my-bets-container").style.display = "block";

    const ticketsList = document.getElementById("tickets-list");
    ticketsList.innerHTML = "<div class='loading-text'>Loading tickets...</div>";

    try {
        const headers = {};
        if (initData) headers["X-Telegram-Init-Data"] = initData;

        const res = await fetch(`/api/sports/my_bets?user_id=${userId}`, { headers });
        const data = await res.json();

        if (data.status === "success" && data.tickets && data.tickets.length > 0) {
            ticketsList.innerHTML = "";
            data.tickets.forEach(ticket => {
                const card = document.createElement("div");
                card.className = "ticket-card";
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; font-size:12px; color:#94a3b8;">
                        <span>ID: ${ticket.id}</span>
                        <span>${(ticket.status || "Pending").toUpperCase()}</span>
                    </div>
                    <div style="margin-top:6px; font-weight:700;">Stake: ${ticket.stake} ETB</div>
                    <div style="margin-top:4px; color:#f59e0b;">Possible win: ${ticket.possible_win} ETB</div>
                `;
                ticketsList.appendChild(card);
            });
        } else {
            ticketsList.innerHTML = "<div class='loading-text'>No tickets yet.</div>";
        }
    } catch (e) {
        console.error(e);
        ticketsList.innerHTML = "<div class='loading-text'>Could not load tickets.</div>";
    }
}

function closeMyBets() {
    document.getElementById("my-bets-container").style.display = "none";
    document.getElementById("matches-list").style.display = "block";
    document.getElementById("hot-picks").style.display = "grid";
}

document.addEventListener("DOMContentLoaded", () => {
    setTabUI();
    setMarketUI();

    document.getElementById("search-input").addEventListener("input", (e) => {
        searchTerm = e.target.value.trim().toLowerCase();
        renderMatches();
        renderHotPicks();
    });

    document.getElementById("favorites-toggle").addEventListener("change", (e) => {
        favoritesOnly = e.target.checked;
        renderMatches();
        renderHotPicks();
    });

    document.getElementById("bet-amount").addEventListener("input", updateBetSlip);
    document.getElementById("clear-slip-btn").addEventListener("click", clearSelections);
    document.getElementById("place-bet-btn").addEventListener("click", placeBet);
    document.getElementById("btn-my-bets").addEventListener("click", showMyBets);

    fetchBalance();
    fetchMatches();
});