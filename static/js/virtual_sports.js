async function fetchMatches() {
    const res = await fetch('/api/get-real-matches');
    const result = await res.json();
    
    const container = document.getElementById("matches-container");
    container.innerHTML = "";

    result.data.forEach(match => {
        if (!match.odds) return; // ኦድስ ከሌለ አታሳየው

        const homeOdds = match.odds.find(o => o.value === "Home").odd;
        const drawOdds = match.odds.find(o => o.value === "Draw").odd;
        const awayOdds = match.odds.find(o => o.value === "Away").odd;

        container.innerHTML += `
            <div class="bg-gray-800 p-4 rounded-xl mb-3">
                <div class="font-bold">${match.teams.home.name} vs ${match.teams.away.name}</div>
                <div class="grid grid-cols-3 gap-2 mt-2">
                    <button onclick="placeBet(..., ${homeOdds})" class="...">1 (${homeOdds})</button>
                    <button onclick="placeBet(..., ${drawOdds})" class="...">X (${drawOdds})</button>
                    <button onclick="placeBet(..., ${awayOdds})" class="...">2 (${awayOdds})</button>
                </div>
            </div>
        `;
    });
}
