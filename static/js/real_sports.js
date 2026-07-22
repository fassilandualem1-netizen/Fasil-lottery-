const tg = window.Telegram ? window.Telegram.WebApp : null;

if (tg) {
    tg.expand();
    tg.ready();
}

// ===== AUTH FOR REAL SPORTS =====
// Get current user from localStorage
let currentUser = null;
try {
    const storedUser = localStorage.getItem('currentUser');
    if (storedUser) {
        currentUser = JSON.parse(storedUser);
    }
} catch (e) {
    console.error('Failed to parse stored user', e);
}

const userId = currentUser ? currentUser.id : (tg?.initDataUnsafe?.user?.id?.toString() || null);
const userName = currentUser ? currentUser.username : (tg?.initDataUnsafe?.user?.first_name || tg?.initDataUnsafe?.user?.username || "የሰፈር ልጅ");
const initData = tg ? tg.initData || "" : "";

const state = {
    balance: 0,
    matches: [],
    selectedBets: {},
    myBets: [],
    currentTab: "top",
    currentMarket: "1x2",
    searchQuery: "",
    selectedLeague: "",
    isMatchesLoading: false
};

const elements = {
    matchesList: document.getElementById("matches-list"),
    slipList: document.getElementById("bet-slip-list"),
    emptySlipState: document.getElementById("empty-slip-state"),
    stakeInput: document.getElementById("bet-amount"),
    slipCount: document.getElementById("slip-count"),
    slipStake: document.getElementById("slip-stake"),
    slipOdds: document.getElementById("slip-odds"),
    slipBaseWin: document.getElementById("slip-base-win"),
    slipBonus: document.getElementById("slip-bonus"),
    possibleWin: document.getElementById("possible-win"),
    statusMessage: document.getElementById("status-message"),
    placeBetBtn: document.getElementById("place-bet-btn"),
    clearSlipBtn: document.getElementById("clear-slip-btn"),
    userBalance: document.getElementById("user-balance"),
    modalBalance: document.getElementById("modal-balance"),
    walletBtn: document.getElementById("wallet-btn"),
    claimWalletBtn: document.getElementById("claim-wallet-btn"),
    walletModal: document.getElementById("wallet-modal"),
    closeWalletBtn: document.getElementById("close-wallet"),
    walletMessage: document.getElementById("wallet-message"),
    walletMethod: document.getElementById("wallet-method"),
    depositAmount: document.getElementById("deposit-amount"),
    depositReceipt: document.getElementById("deposit-receipt"),
    depositBtn: document.getElementById("deposit-btn"),
    withdrawBank: document.getElementById("withdraw-bank"),
    withdrawName: document.getElementById("withdraw-name"),
    withdrawAccount: document.getElementById("withdraw-account"),
    withdrawAmount: document.getElementById("withdraw-amount"),
    withdrawBtn: document.getElementById("withdraw-btn"),
    confirmModal: document.getElementById("confirm-modal"),
    confirmSummary: document.getElementById("confirm-summary"),
    closeConfirmBtn: document.getElementById("close-confirm"),
    confirmBetBtn: document.getElementById("confirm-bet-btn"),
    cancelBetBtn: document.getElementById("cancel-bet-btn"),
    myBetsBtn: document.getElementById("my-bets-btn"),
    myBetsList: document.getElementById("my-bets-list"),
    myBetsModal: document.getElementById("my-bets-modal"),
    myBetsModalContent: document.getElementById("my-bets-modal-content"),
    closeMyBetsBtn: document.getElementById("close-my-bets"),
    tabTop: document.getElementById("tab-top"),
    tabUpcoming: document.getElementById("tab-upcoming"),
    market1x2: document.getElementById("market-1x2"),
    marketDc: document.getElementById("market-dc"),
    matchSearch: document.getElementById("match-search"),
    refreshMatchesBtn: document.getElementById("refresh-matches-btn"),
    selectedLeagueLabel: document.getElementById("selected-league-label"),
    topLeaguesList: document.getElementById("top-leagues-list"),
    toast: document.getElementById("toast")
};

bindEvents();
bootstrap();

function bindEvents() {
    elements.tabTop?.addEventListener("click", () => switchTab("top"));
    elements.tabUpcoming?.addEventListener("click", () => switchTab("upcoming"));
    elements.market1x2?.addEventListener("click", () => switchMarket("1x2"));
    elements.marketDc?.addEventListener("click", () => switchMarket("dc"));

    elements.stakeInput?.addEventListener("input", updateBetSlip);
    elements.matchSearch?.addEventListener("input", (event) => {
        state.searchQuery = event.target.value.trim().toLowerCase();
        renderMatches();
        renderTopLeagues();
    });
    elements.refreshMatchesBtn?.addEventListener("click", () => fetchMatches(true));
    elements.clearSlipBtn?.addEventListener("click", clearSlip);
    elements.placeBetBtn?.addEventListener("click", openConfirmModal);
    elements.confirmBetBtn?.addEventListener("click", placeBet);
    elements.cancelBetBtn?.addEventListener("click", closeConfirmModal);
    elements.closeConfirmBtn?.addEventListener("click", closeConfirmModal);

    elements.walletBtn?.addEventListener("click", openWalletModal);
    elements.claimWalletBtn?.addEventListener("click", openWalletModal);
    elements.closeWalletBtn?.addEventListener("click", closeWalletModal);
    elements.depositBtn?.addEventListener("click", handleDeposit);
    elements.withdrawBtn?.addEventListener("click", handleWithdraw);

    elements.myBetsBtn?.addEventListener("click", openMyBetsModal);
    elements.closeMyBetsBtn?.addEventListener("click", closeMyBetsModal);

    elements.walletModal?.addEventListener("click", (event) => {
        if (event.target === elements.walletModal) closeWalletModal();
    });

    elements.confirmModal?.addEventListener("click", (event) => {
        if (event.target === elements.confirmModal) closeConfirmModal();
    });

    elements.myBetsModal?.addEventListener("click", (event) => {
        if (event.target === elements.myBetsModal) closeMyBetsModal();
    });

    document.querySelectorAll(".stake-chip").forEach((button) => {
        button.addEventListener("click", () => {
            if (elements.stakeInput) {
                elements.stakeInput.value = button.dataset.stake || "20";
                updateBetSlip();
            }
        });
    });
}

async function bootstrap() {
    updateTabButtons();
    updateMarketButtons();
    updateBetSlip();

    await Promise.all([loadBalance(), loadMyBets()]);
    await fetchMatches();
}

async function secureFetch(url, options = {}) {
    const nextOptions = { ...options, headers: { ...(options.headers || {}) } };

    if (initData) {
        nextOptions.headers["X-Telegram-Init-Data"] = initData;
    }

    if (nextOptions.body && !(nextOptions.body instanceof FormData) && !nextOptions.headers["Content-Type"]) {
        nextOptions.headers["Content-Type"] = "application/json";
    }

    return fetch(url, nextOptions);
}

function formatLocalTime(apiDateStr, apiTimeStr) {
    if (!apiDateStr || apiDateStr === "TBA") {
        return { date: "TBA", time: apiTimeStr || "TBA" };
    }

    const today = new Date();
    const matchDate = new Date(apiDateStr);
    const tomorrow = new Date(today);
    tomorrow.setDate(today.getDate() + 1);

    let label = `${matchDate.getDate().toString().padStart(2, "0")}/${(matchDate.getMonth() + 1).toString().padStart(2, "0")}`;

    if (matchDate.toDateString() === today.toDateString()) {
        label = "ዛሬ";
    } else if (matchDate.toDateString() === tomorrow.toDateString()) {
        label = "ነገ";
    }

    return { date: label, time: apiTimeStr || "TBA" };
}

function switchTab(tab) {
    state.currentTab = tab;
    updateTabButtons();
    fetchMatches();
}

function switchMarket(market) {
    state.currentMarket = market;
    updateMarketButtons();
    renderMatches();
}

function updateTabButtons() {
    const activeClasses = ["bg-[#ffcc00]", "text-black"];
    const inactiveClasses = ["text-zinc-300", "hover:bg-zinc-700", "transition"];

    [elements.tabTop, elements.tabUpcoming].forEach((button) => {
        button?.classList.remove(...activeClasses, ...inactiveClasses);
        button?.classList.add(...inactiveClasses);
    });

    if (state.currentTab === "top") {
        elements.tabTop?.classList.remove(...inactiveClasses);
        elements.tabTop?.classList.add(...activeClasses);
    } else {
        elements.tabUpcoming?.classList.remove(...inactiveClasses);
        elements.tabUpcoming?.classList.add(...activeClasses);
    }
}

function updateMarketButtons() {
    const activeClasses = ["bg-yellow-400", "text-black", "border-yellow-400"];
    const inactiveClasses = ["bg-[#2b2b2b]", "text-zinc-300", "border-zinc-700"];

    [elements.market1x2, elements.marketDc].forEach((button) => {
        button?.classList.remove(...activeClasses, ...inactiveClasses);
        button?.classList.add(...inactiveClasses);
    });

    const activeButton = state.currentMarket === "1x2" ? elements.market1x2 : elements.marketDc;
    activeButton?.classList.remove(...inactiveClasses);
    activeButton?.classList.add(...activeClasses);
}

async function loadBalance() {
    try {
        const response = await secureFetch("/api/get_balance", {
            method: "POST",
            body: JSON.stringify({ user_id: userId })
        });
        const data = await response.json();

        if (data.status === "success") {
            state.balance = Number(data.balance || 0);
            updateBalanceDisplay();
        }
    } catch (error) {
        console.error("Failed to load balance:", error);
    }
}

async function fetchMatches(showRefreshToast = false) {
    if (!elements.matchesList) return;

    state.isMatchesLoading = true;
    elements.matchesList.innerHTML = `
        <div class="text-center py-10 text-zinc-400 text-sm flex flex-col items-center gap-3">
            <div class="loading-spinner"></div>
            <span>Loading matches...</span>
        </div>
    `;

    try {
        const response = await secureFetch(`/api/sports/odds?tab=${state.currentTab}`);
        const data = await response.json();

        state.matches = Array.isArray(data.matches) && data.matches.length ? data.matches : getFallbackMatches();
        state.selectedLeague = "";
        renderTopLeagues();
        renderMatches();
        if (showRefreshToast) {
            showToast("Matches refreshed.");
        }
    } catch (error) {
        console.error("Failed to load matches:", error);
        state.matches = getFallbackMatches();
        renderTopLeagues();
        renderMatches();
        showToast("Fallback matches loaded.");
    } finally {
        state.isMatchesLoading = false;
    }
}

function renderTopLeagues() {
    if (!elements.topLeaguesList) return;

    const seen = new Set();
    const leagues = [];

    state.matches.forEach((match) => {
        const league = match.fixture?.league;
        if (league && !seen.has(league)) {
            seen.add(league);
            leagues.push(league);
        }
    });

    const activeLeague = state.selectedLeague;
    const leagueButtons = [
        { label: "All Leagues", value: "" },
        ...leagues.slice(0, 8).map((league) => ({ label: league, value: league }))
    ];

    elements.topLeaguesList.innerHTML = leagueButtons.map((league) => `
        <li>
            <button type="button" class="league-filter w-full px-3 py-2 flex items-center justify-between hover:bg-zinc-800 transition text-left ${activeLeague === league.value ? "league-filter-active" : ""}" data-league="${escapeHtml(league.value)}">
                <span>${escapeHtml(league.label)}</span>
                <span class="text-zinc-500">›</span>
            </button>
        </li>
    `).join("");

    elements.topLeaguesList.querySelectorAll(".league-filter").forEach((button) => {
        button.addEventListener("click", () => {
            state.selectedLeague = button.dataset.league || "";
            renderTopLeagues();
            renderMatches();
        });
    });
}

function getVisibleMatches() {
    const query = state.searchQuery;

    return state.matches.filter((match) => {
        const home = match.fixture?.teams?.home?.name || "";
        const away = match.fixture?.teams?.away?.name || "";
        const league = match.fixture?.league || "";
        const leagueMatches = !state.selectedLeague || league === state.selectedLeague;
        const searchMatches = !query || `${home} ${away} ${league}`.toLowerCase().includes(query);
        return leagueMatches && searchMatches;
    });
}

function getMarketButtons(match, home, away) {
    const odds = match.odds || {};
    const matchId = String(match.fixture?.id || Math.random().toString(36).slice(2));
    const selectedPick = state.selectedBets[matchId]?.pick;
    const market = state.currentMarket;

    const options = market === "dc"
        ? [
            { pick: "1x", label: "1X", value: odds.dc_1x, team: "1X" },
            { pick: "12", label: "12", value: odds.dc_12, team: "12" },
            { pick: "x2", label: "X2", value: odds.dc_x2, team: "X2" }
        ]
        : [
            { pick: "home", label: "1", value: odds.home, team: home },
            { pick: "draw", label: "X", value: odds.draw, team: "Draw" },
            { pick: "away", label: "2", value: odds.away, team: away }
        ];

    return options.map((option) => {
        const isDisabled = !option.value;
        const isActive = selectedPick === option.pick;
        const classes = isDisabled
            ? "bg-[#232323] border border-zinc-800 text-zinc-500 cursor-not-allowed"
            : isActive
                ? "bg-yellow-400 border border-yellow-300 text-black"
                : "bg-[#2b2b2b] border border-zinc-700 text-white hover:border-yellow-400";

        return `
            <button
                type="button"
                class="odds-btn py-2 px-2 rounded flex justify-between items-center transition ${classes}"
                data-match-id="${escapeHtml(matchId)}"
                data-pick="${escapeHtml(option.pick)}"
                data-odd="${option.value || ""}"
                data-team="${escapeHtml(option.team)}"
                data-home-team="${escapeHtml(home)}"
                data-away-team="${escapeHtml(away)}"
                data-league="${escapeHtml(match.fixture?.league || "Unknown League")}"
                data-market="${market}"
                ${isDisabled ? "disabled" : ""}
            >
                <span class="text-[10px] font-bold">${option.label}</span>
                <span class="text-xs font-bold">${option.value ? Number(option.value).toFixed(2) : "-"}</span>
            </button>
        `;
    }).join("");
}

function renderMatches() {
    if (!elements.matchesList) return;

    const matches = getVisibleMatches();
    if (elements.selectedLeagueLabel) {
        elements.selectedLeagueLabel.textContent = state.selectedLeague || "All leagues";
    }

    if (!matches.length) {
        elements.matchesList.innerHTML = `
            <div class="text-center py-10 text-zinc-400 text-sm">
                No matches found for the current filter.
            </div>
        `;
        return;
    }

    elements.matchesList.innerHTML = matches.map((match) => {
        const home = match.fixture?.teams?.home?.name || "Home Team";
        const away = match.fixture?.teams?.away?.name || "Away Team";
        const league = match.fixture?.league || "Unknown League";
        const timeInfo = formatLocalTime(match.fixture?.date, match.fixture?.time);

        return `
            <article class="p-3 border-b border-zinc-800 hover:bg-[#252525] transition">
                <div class="flex justify-between items-center text-xs mb-2">
                    <span class="text-zinc-400 font-medium truncate">${escapeHtml(league)}</span>
                    <span class="text-zinc-500 text-[11px]">${escapeHtml(timeInfo.date)} ${escapeHtml(timeInfo.time)}</span>
                </div>
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                        <h3 class="font-bold text-sm text-zinc-100">${escapeHtml(home)} vs ${escapeHtml(away)}</h3>
                        <span class="inline-block mt-1 text-[10px] bg-zinc-800 text-yellow-400 px-1.5 py-0.5 rounded border border-zinc-700">
                            ${state.currentMarket === "dc" ? "Double Chance" : "1X2 Market"}
                        </span>
                    </div>
                    <div class="grid grid-cols-3 gap-1.5 sm:min-w-[220px]">
                        ${getMarketButtons(match, home, away)}
                    </div>
                </div>
            </article>
        `;
    }).join("");

    elements.matchesList.querySelectorAll(".odds-btn").forEach((button) => {
        button.addEventListener("click", () => {
            toggleSelection({
                matchId: button.dataset.matchId,
                pick: button.dataset.pick,
                odd: Number(button.dataset.odd),
                team: button.dataset.team,
                homeTeam: button.dataset.homeTeam,
                awayTeam: button.dataset.awayTeam,
                league: button.dataset.league,
                market: button.dataset.market
            });
        });
    });
}

function toggleSelection(selection) {
    const matchLabel = `${selection.homeTeam} vs ${selection.awayTeam}`;
    const currentSelection = state.selectedBets[selection.matchId];

    if (currentSelection?.pick === selection.pick) {
        delete state.selectedBets[selection.matchId];
        setStatus("Selection removed from your betslip.");
    } else {
        state.selectedBets[selection.matchId] = {
            matchId: selection.matchId,
            pick: selection.pick,
            odd: selection.odd,
            team: selection.team,
            homeTeam: selection.homeTeam,
            awayTeam: selection.awayTeam,
            league: selection.league,
            market: selection.market,
            matchLabel
        };
        setStatus(`${selection.team} added to your betslip.`);
    }

    renderMatches();
    updateBetSlip();
}

function updateBetSlip() {
    const selections = Object.values(state.selectedBets);
    const stake = Number(elements.stakeInput?.value || 0);
    const selectionCount = selections.length;
    const totalOdds = selectionCount
        ? selections.reduce((total, item) => total * Number(item.odd || 1), 1)
        : 0;
    const bonusPercent = selectionCount >= 10 ? 10 : selectionCount >= 5 ? 7 : selectionCount >= 3 ? 5 : 0;
    const baseWin = stake * totalOdds;
    const bonusAmount = baseWin * (bonusPercent / 100);
    const possibleWin = baseWin + bonusAmount;

    if (elements.slipCount) elements.slipCount.textContent = String(selectionCount);
    if (elements.slipStake) elements.slipStake.textContent = `${stake.toFixed(2)} ETB`;
    if (elements.slipOdds) elements.slipOdds.textContent = selectionCount ? totalOdds.toFixed(2) : "0.00";
    if (elements.slipBaseWin) elements.slipBaseWin.textContent = `${baseWin.toFixed(2)} ETB`;
    if (elements.slipBonus) elements.slipBonus.textContent = `${bonusPercent}% (${bonusAmount.toFixed(2)} ETB)`;
    if (elements.possibleWin) elements.possibleWin.textContent = `${possibleWin.toFixed(2)} ETB`;

    if (elements.emptySlipState) {
        elements.emptySlipState.classList.toggle("hidden", selectionCount > 0);
    }

    if (elements.slipList) {
        elements.slipList.innerHTML = selections.map((item) => `
            <div class="bg-zinc-800/60 border border-zinc-700 rounded p-3">
                <div class="flex justify-between items-start gap-3">
                    <div>
                        <div class="text-xs font-semibold text-yellow-400">${escapeHtml(item.team)}</div>
                        <div class="text-xs text-zinc-300 mt-1">${escapeHtml(item.matchLabel)}</div>
                        <div class="text-[11px] text-zinc-500 mt-1">${escapeHtml(item.market === "dc" ? "Double Chance" : "1X2")} • ${Number(item.odd).toFixed(2)}</div>
                    </div>
                    <button type="button" class="remove-slip text-zinc-500 hover:text-red-400 text-sm" data-match-id="${escapeHtml(item.matchId)}">&times;</button>
                </div>
            </div>
        `).join("");

        elements.slipList.querySelectorAll(".remove-slip").forEach((button) => {
            button.addEventListener("click", () => {
                delete state.selectedBets[button.dataset.matchId];
                renderMatches();
                updateBetSlip();
            });
        });
    }

    if (elements.placeBetBtn) {
        const enabled = selectionCount > 0 && stake >= 10;
        elements.placeBetBtn.disabled = !enabled;
        elements.placeBetBtn.className = enabled
            ? "flex-1 bg-yellow-400 hover:bg-yellow-500 text-black font-bold text-xs py-2 rounded uppercase transition"
            : "flex-1 bg-zinc-700 text-zinc-500 font-bold text-xs py-2 rounded uppercase cursor-not-allowed";
    }

    document.querySelectorAll(".stake-chip").forEach((button) => {
        button.classList.toggle("stake-chip-active", Number(button.dataset.stake) === stake);
    });
}

function clearSlip() {
    state.selectedBets = {};
    renderMatches();
    updateBetSlip();
    setStatus("The betslip has been cleared.");
}

function openConfirmModal() {
    const selections = Object.values(state.selectedBets);
    const stake = Number(elements.stakeInput?.value || 0);

    if (!selections.length) {
        showToast("Add at least one match first.");
        return;
    }

    if (stake < 10) {
        showToast("Minimum stake is 10 ETB.");
        return;
    }

    if (stake > state.balance) {
        showToast("Insufficient balance.");
        return;
    }

    const totalOdds = selections.reduce((total, item) => total * Number(item.odd || 1), 1);
    const bonusPercent = selections.length >= 10 ? 10 : selections.length >= 5 ? 7 : selections.length >= 3 ? 5 : 0;
    const baseWin = stake * totalOdds;
    const bonusAmount = baseWin * (bonusPercent / 100);
    const possibleWin = baseWin + bonusAmount;

    if (elements.confirmSummary) {
        elements.confirmSummary.innerHTML = `
            <div class="space-y-2 text-sm text-zinc-200">
                <div><span class="text-zinc-400">Stake:</span> <strong>${stake.toFixed(2)} ETB</strong></div>
                <div><span class="text-zinc-400">Selections:</span> <strong>${selections.length}</strong></div>
                <div><span class="text-zinc-400">Total Odds:</span> <strong>${totalOdds.toFixed(2)}</strong></div>
                <div><span class="text-zinc-400">Bonus:</span> <strong>${bonusPercent}% (${bonusAmount.toFixed(2)} ETB)</strong></div>
                <div><span class="text-zinc-400">Possible Win:</span> <strong class="text-yellow-400">${possibleWin.toFixed(2)} ETB</strong></div>
                <div class="border-t border-zinc-700 pt-2 mt-2 space-y-1">
                    ${selections.map((item) => `
                        <div class="text-xs">
                            <span class="text-yellow-400">${escapeHtml(item.team)}</span>
                            <span class="text-zinc-500"> • </span>
                            <span>${escapeHtml(item.matchLabel)}</span>
                            <span class="text-zinc-500"> • ${Number(item.odd).toFixed(2)}</span>
                        </div>
                    `).join("")}
                </div>
            </div>
        `;
    }

    elements.confirmModal?.classList.remove("hidden");
    elements.confirmModal?.classList.add("flex");
}

function closeConfirmModal() {
    elements.confirmModal?.classList.add("hidden");
    elements.confirmModal?.classList.remove("flex");
}

async function placeBet() {
    const selections = Object.values(state.selectedBets);
    const stake = Number(elements.stakeInput?.value || 0);

    if (!selections.length || stake < 10) {
        showToast("Please add selections and valid stake.");
        return;
    }

    const resetConfirmButton = setButtonLoading(elements.confirmBetBtn, "Placing...");

    try {
        const response = await secureFetch("/api/sports/place_bet", {
            method: "POST",
            body: JSON.stringify({
                user_id: userId,
                bet_amount: stake,
                selections: selections.map((item) => ({
                    match_id: item.matchId,
                    pick: item.pick,
                    odd: item.odd,
                    team: item.team,
                    home_team: item.homeTeam,
                    away_team: item.awayTeam,
                    league: item.league,
                    market: item.market
                }))
            })
        });

        const data = await response.json();

        if (data.status === "success") {
            state.balance = Number(data.balance || Math.max(0, state.balance - stake));
            state.selectedBets = {};
            updateBalanceDisplay();
            updateBetSlip();
            closeConfirmModal();
            await loadMyBets();
            renderMatches();
            setStatus(`Ticket ${data.ticket_id} placed successfully.`);
            showToast(`Ticket ${data.ticket_id} placed.`);
            return;
        }

        showToast(data.message || "Failed to place bet.");
    } catch (error) {
        console.error("Bet placement failed:", error);
        showToast("Failed to place bet.");
    } finally {
        resetConfirmButton();
    }
}

async function loadMyBets() {
    try {
        const response = await secureFetch(`/api/sports/my_bets?user_id=${encodeURIComponent(userId)}`);
        const data = await response.json();

        state.myBets = data.status === "success" ? (data.tickets || []) : [];
        renderMyBets();
    } catch (error) {
        console.error("Failed to load my bets:", error);
    }
}

function renderTicket(ticket) {
    const status = String(ticket.status || "pending").toLowerCase();
    const statusColor = status.includes("won")
        ? "text-green-400"
        : status.includes("lost")
            ? "text-red-400"
            : "text-yellow-400";

    return `
        <div class="ticket-card bg-zinc-800/40 border border-zinc-700 rounded p-3 text-xs">
            <div class="flex justify-between items-start gap-3">
                <div>
                    <div class="font-semibold text-yellow-400">${escapeHtml(ticket.id || "Ticket")}</div>
                    <div class="text-zinc-400 mt-1">${ticket.placed_at || ""}</div>
                </div>
                <div class="${statusColor} font-semibold uppercase">${escapeHtml(status)}</div>
            </div>
            <div class="grid grid-cols-2 gap-2 mt-3 text-zinc-300">
                <div>Stake: <span class="text-white">${Number(ticket.stake || 0).toFixed(2)} ETB</span></div>
                <div>Odds: <span class="text-white">${Number(ticket.total_odds || 0).toFixed(2)}</span></div>
                <div>Selections: <span class="text-white">${ticket.selection_count || ticket.selections?.length || 0}</span></div>
                <div>Win: <span class="text-yellow-400">${Number(ticket.possible_win || 0).toFixed(2)} ETB</span></div>
            </div>
            <div class="mt-2 text-[11px] text-zinc-400">
                Base Win: ${Number(ticket.base_win || 0).toFixed(2)} ETB • Bonus: ${Number(ticket.bonus_percent || 0)}%
            </div>
            <div class="border-t border-zinc-700 mt-3 pt-2 space-y-1">
                ${(ticket.selections || []).map((selection) => `
                    <div class="flex justify-between gap-2 text-[11px] text-zinc-300">
                        <span>${escapeHtml(selection.home_team || "")}${selection.home_team ? " vs " : ""}${escapeHtml(selection.away_team || selection.team || "")} • ${escapeHtml((selection.team || selection.pick || "").toUpperCase())}</span>
                        <span class="text-yellow-400">${Number(selection.odd || 0).toFixed(2)}</span>
                    </div>
                `).join("")}
            </div>
        </div>
    `;
}

function renderMyBets() {
    const emptyMarkup = `<p class="text-xs text-zinc-500">No bets placed yet.</p>`;
    const markup = state.myBets.length ? state.myBets.map(renderTicket).join("") : emptyMarkup;

    if (elements.myBetsList) {
        elements.myBetsList.innerHTML = markup;
    }

    if (elements.myBetsModalContent) {
        elements.myBetsModalContent.innerHTML = markup;
    }
}

function openMyBetsModal() {
    loadMyBets();
    elements.myBetsModal?.classList.remove("hidden");
    elements.myBetsModal?.classList.add("flex");
}

function closeMyBetsModal() {
    elements.myBetsModal?.classList.add("hidden");
    elements.myBetsModal?.classList.remove("flex");
}

async function openWalletModal() {
    elements.walletMessage.textContent = "";
    elements.walletModal?.classList.remove("hidden");
    elements.walletModal?.classList.add("flex");
    await loadWithdrawInfo();
}

function closeWalletModal() {
    elements.walletModal?.classList.add("hidden");
    elements.walletModal?.classList.remove("flex");
}

async function loadWithdrawInfo() {
    try {
        const response = await secureFetch("/api/get_withdraw_info", {
            method: "POST",
            body: JSON.stringify({ user_id: userId })
        });
        const data = await response.json();
        const info = data.info || {};

        if (elements.withdrawBank && info.bank_name) elements.withdrawBank.value = info.bank_name;
        if (elements.withdrawName && info.account_name) elements.withdrawName.value = info.account_name;
        if (elements.withdrawAccount && info.phone) elements.withdrawAccount.value = info.phone;
    } catch (error) {
        console.error("Failed to load withdraw info:", error);
    }
}

async function handleDeposit() {
    const amount = Number(elements.depositAmount?.value || 0);
    const receiptFile = elements.depositReceipt?.files?.[0];
    const method = elements.walletMethod?.value || "telebirr";

    if (amount <= 0 || !receiptFile) {
        setWalletMessage("Enter amount and upload receipt screenshot.", true);
        return;
    }

    const formData = new FormData();
    formData.append("user_id", userId);
    formData.append("user_name", userName);
    formData.append("amount", amount);
    formData.append("method", method);
    formData.append("receipt", receiptFile);

    const resetDepositButton = setButtonLoading(elements.depositBtn, "Submitting...");
    try {
        const response = await secureFetch("/api/deposit", {
            method: "POST",
            body: formData
        });
        const data = await response.json();

        if (data.status === "success") {
            setWalletMessage("Deposit request sent to admin.", false);
            showToast("Deposit request submitted.");
            elements.depositAmount.value = "100";
            if (elements.depositReceipt) elements.depositReceipt.value = "";
            return;
        }

        setWalletMessage(data.message || "Deposit failed.", true);
    } catch (error) {
        console.error("Deposit failed:", error);
        setWalletMessage("Deposit failed. Try again.", true);
    } finally {
        resetDepositButton();
    }
}

async function handleWithdraw() {
    const amount = Number(elements.withdrawAmount?.value || 0);
    const payload = {
        user_id: userId,
        user_name: userName,
        bank_name: elements.withdrawBank?.value || "",
        account_name: elements.withdrawName?.value || "",
        phone: elements.withdrawAccount?.value || "",
        amount
    };

    if (amount <= 0 || !payload.bank_name || !payload.account_name || !payload.phone) {
        setWalletMessage("Fill all withdraw fields first.", true);
        return;
    }

    const resetWithdrawButton = setButtonLoading(elements.withdrawBtn, "Submitting...");
    try {
        const response = await secureFetch("/api/withdraw", {
            method: "POST",
            body: JSON.stringify(payload)
        });
        const data = await response.json();

        if (data.status === "success") {
            setWalletMessage(data.message || "Withdraw request sent.", false);
            showToast("Withdraw request submitted.");
            await loadBalance();
            return;
        }

        setWalletMessage(data.message || "Withdraw failed.", true);
    } catch (error) {
        console.error("Withdraw failed:", error);
        setWalletMessage("Withdraw failed. Try again.", true);
    } finally {
        resetWithdrawButton();
    }
}

function updateBalanceDisplay() {
    const label = `Balance: ${state.balance.toFixed(2)} ETB`;
    if (elements.userBalance) elements.userBalance.textContent = label;
    if (elements.modalBalance) elements.modalBalance.textContent = `${state.balance.toFixed(2)} ETB`;
}

function setStatus(message) {
    if (elements.statusMessage) {
        elements.statusMessage.textContent = message;
    }
}

function setWalletMessage(message, isError) {
    if (!elements.walletMessage) return;

    elements.walletMessage.textContent = message;
    elements.walletMessage.className = isError ? "text-xs text-red-400" : "text-xs text-green-400";
}

function showToast(message) {
    if (!elements.toast) return;

    elements.toast.textContent = message;
    elements.toast.classList.remove("hidden");
    clearTimeout(showToast.timeoutId);
    showToast.timeoutId = setTimeout(() => {
        elements.toast.classList.add("hidden");
    }, 3000);
}

function setButtonLoading(button, loadingText) {
    if (!button) {
        return () => {};
    }

    const originalText = button.textContent;
    button.textContent = loadingText;
    button.disabled = true;

    return () => {
        button.textContent = originalText;
        button.disabled = false;
    };
}

function getFallbackMatches() {
    return [
        {
            fixture: {
                id: "ethiopian-demo-1",
                teams: { home: { name: "Saint George SC" }, away: { name: "Fasil Kenema SC" } },
                league: "Ethiopian Premier League",
                date: "2026-07-22",
                time: "16:00"
            },
            odds: { home: 2.1, draw: 3.2, away: 3.5, dc_1x: 1.35, dc_12: 1.42, dc_x2: 1.68 }
        },
        {
            fixture: {
                id: "europe-demo-1",
                teams: { home: { name: "FC Basel" }, away: { name: "Viking Stavanger" } },
                league: "UEFA Conference League - Qualification",
                date: "2026-07-23",
                time: "19:00"
            },
            odds: { home: 1.95, draw: 3.4, away: 3.8, dc_1x: 1.32, dc_12: 1.38, dc_x2: 1.78 }
        },
        {
            fixture: {
                id: "england-demo-1",
                teams: { home: { name: "Arsenal" }, away: { name: "Brighton" } },
                league: "English Premier League",
                date: "2026-07-24",
                time: "15:00"
            },
            odds: { home: 1.85, draw: 3.5, away: 4.2, dc_1x: 1.30, dc_12: 1.35, dc_x2: 1.90 }
        }
    ];
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}
