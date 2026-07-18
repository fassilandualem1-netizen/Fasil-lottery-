async function fetchMatches() {
    const res = await fetch('/api/get-real-matches');
    const result = await res.json();
    console.log(result.data); // ጨዋታዎቹ እዚህ ይመጣሉ
    // አሁን እነዚህን ጨዋታዎች በ Loop ተጠቅመህ real_sports.html ላይ ማሳየት ትችላለህ
}
fetchMatches();
