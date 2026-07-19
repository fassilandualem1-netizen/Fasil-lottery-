// የጨዋታው ወቅታዊ መረጃ ማከማቻ
let gameRepository = {
    state: "WAITING", // WAITING, FLYING, CRASHED
    currentRoundBets: [], // የአሁኑ ዙር ተወራራሾች
    nextRoundBets: []     // ለቀጣይ ዙር ተሰልፈው የሚጠብቁ
};

// ውርርድ መቀበያ ኤፒአይ (Place Bet API)
app.post('/place_bet', (req, res) => {
    const { userId, amount } = req.body;
    
    if (gameRepository.state === "WAITING") {
        gameRepository.currentRoundBets.push({ userId, amount });
        return res.json({ status: "SUCCESS", message: "በአሁኑ ዙር ተሳትፈሃል!" });
    } else {
        // ጨዋታው ከተጀመረ ወደ ቀጣዩ ዙር ሰሌዳ ይላካል
        gameRepository.nextRoundBets.push({ userId, amount });
        return res.json({ status: "QUEUED", message: "ለውርርድ ለቀጣዩ ዙር ተመዝግበሃል!" });
    }
});

// ጨዋታው ተከስክሶ አዲስ ዙር ሲጀምር የሚጠራ ፈንክሽን
function startNewRound() {
    gameRepository.state = "WAITING";
    // የቀጣይ ዙር የነበሩትን ወደ አሁኑ ዙር ማዛወር
    gameRepository.currentRoundBets = [...gameRepository.nextRoundBets];
    gameRepository.nextRoundBets = []; // ማጽዳት
}
