import express from 'express';
import cors from 'cors';
import path from 'path';
import multer from 'multer';
import crypto from 'crypto';
import { createServer as createViteServer } from 'vite';

const app = express();
const PORT = process.env.PORT || 3000;
const ADMIN_TELEGRAM_ID = process.env.ADMIN_TELEGRAM_ID || '8488592165';
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '';

app.use(cors());
app.use(express.json({ limit: '25mb' }));
app.use(express.urlencoded({ extended: true, limit: '25mb' }));

// Multer memory storage for deposit receipt screenshot uploads
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 15 * 1024 * 1024 }, // 15MB max
});

/**
 * Server-Side Cryptographically Secure RNG Game Logic
 */
function generateSecureServerSeed(): string {
  return crypto.randomBytes(32).toString('hex');
}

function hashServerSeed(seed: string): string {
  return crypto.createHash('sha256').update(seed).digest('hex');
}

function getSecureGameFloat(serverSeed: string, clientSeed: string, nonce: number): number {
  const hmac = crypto.createHmac('sha256', serverSeed).update(`${clientSeed}:${nonce}`).digest('hex');
  const subHash = hmac.substring(0, 8);
  const decimal = parseInt(subHash, 16);
  return decimal / 4294967296; // 2^32
}

// Aviator Crash Multiplier
function calculateAviatorCrash(serverSeed: string, clientSeed: string, nonce: number): number {
  const rand = getSecureGameFloat(serverSeed, clientSeed, nonce);
  const houseEdge = 0.03; // 3% house edge
  if (rand < houseEdge) return 1.00; // Instant crash
  const raw = (100 * (1 - houseEdge)) / (100 - rand * 100);
  return Math.max(1.00, Math.floor(raw * 100) / 100);
}

// Keno Draw (20 unique numbers out of 1-80)
function calculateKenoDraw(serverSeed: string, clientSeed: string, nonce: number): number[] {
  const drawn: number[] = [];
  let currentNonce = nonce;
  while (drawn.length < 20) {
    const float = getSecureGameFloat(serverSeed, clientSeed, currentNonce++);
    const num = Math.floor(float * 80) + 1;
    if (!drawn.includes(num)) {
      drawn.push(num);
    }
  }
  return drawn.sort((a, b) => a - b);
}

// Dice Roll (0.00 - 100.00)
function calculateDiceRoll(serverSeed: string, clientSeed: string, nonce: number): number {
  const float = getSecureGameFloat(serverSeed, clientSeed, nonce);
  return Math.floor(float * 10000) / 100;
}

// Coinflip ('HEADS' | 'TAILS')
function calculateCoinflip(serverSeed: string, clientSeed: string, nonce: number): 'HEADS' | 'TAILS' {
  const float = getSecureGameFloat(serverSeed, clientSeed, nonce);
  return float < 0.5 ? 'HEADS' : 'TAILS';
}

// Mines Grid (25 tiles, mineCount mines)
function calculateMinesGrid(serverSeed: string, clientSeed: string, nonce: number, mineCount: number): boolean[] {
  const grid = new Array(25).fill(false);
  let placed = 0;
  let currentNonce = nonce;
  while (placed < mineCount) {
    const float = getSecureGameFloat(serverSeed, clientSeed, currentNonce++);
    const index = Math.floor(float * 25);
    if (!grid[index]) {
      grid[index] = true;
      placed++;
    }
  }
  return grid;
}

// Color Wheel Segment (Multipliers: 0x, 1.2x, 1.5x, 2x, 3x, 5x, 10x, 25x, 50x)
const COLOR_WHEEL_SEGMENTS = [1.2, 0, 1.5, 2.0, 0, 3.0, 1.2, 5.0, 0, 10.0, 2.0, 25.0, 0, 50.0, 1.5, 3.0];
function calculateColorWheel(serverSeed: string, clientSeed: string, nonce: number): { index: number; multiplier: number } {
  const float = getSecureGameFloat(serverSeed, clientSeed, nonce);
  const index = Math.floor(float * COLOR_WHEEL_SEGMENTS.length);
  return { index, multiplier: COLOR_WHEEL_SEGMENTS[index] };
}

// Utility to send requests to Telegram Bot API
async function callTelegramApi(method: string, payload: any, isFormData = false) {
  if (!TELEGRAM_BOT_TOKEN) {
    console.warn(`[Telegram Bot] Token not set. Mocking API call for method: ${method}`);
    return { ok: true, mocked: true };
  }

  try {
    const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/${method}`;
    let response;

    if (isFormData) {
      response = await fetch(url, {
        method: 'POST',
        body: payload,
      });
    } else {
      response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }

    const data = await response.json();
    return data;
  } catch (err) {
    console.error(`[Telegram Bot Error] ${method}:`, err);
    return { ok: false, error: String(err) };
  }
}

/**
 * Handle Telegram Bot Commands (/start, /admin, /pending, /stats)
 */
async function handleBotUpdate(update: any, appUrl: string) {
  if (update.message) {
    const msg = update.message;
    const chatId = msg.chat.id;
    const userId = String(msg.from?.id || chatId);
    const text = (msg.text || '').trim();

    const isAdminUser = userId === ADMIN_TELEGRAM_ID;

    if (text.startsWith('/start')) {
      if (isAdminUser) {
        await callTelegramApi('sendMessage', {
          chat_id: chatId,
          text: `Welcome Admin! 👑\n\nYou are logged in as the official Yegna Bet Administrator.\nUse the dashboard below to verify pending deposit screenshot receipts, manage withdrawals, and view live platform statistics.`,
          reply_markup: {
            inline_keyboard: [
              [
                {
                  text: 'Open Admin Dashboard 📊',
                  web_app: { url: appUrl },
                },
              ],
              [
                { text: 'Pending Queue ⏳', callback_data: 'cmd_pending' },
                { text: 'Live Stats 📈', callback_data: 'cmd_stats' },
              ],
            ],
          },
        });
      } else {
        await callTelegramApi('sendMessage', {
          chat_id: chatId,
          text: `Welcome to Yegna Bet! 🎮\n\nEthiopia's premier 24/7 multiplayer gaming platform! Play Aviator, Virtual Sports, Keno, Coinflip, Mines, Dice, and Color Wheel with instant Telebirr & CBE deposits.`,
          reply_markup: {
            inline_keyboard: [
              [
                {
                  text: 'Play Now / ተጫወት 🎮',
                  web_app: { url: appUrl },
                },
              ],
            ],
          },
        });
      }
    } else if (text === '/admin') {
      if (isAdminUser) {
        await callTelegramApi('sendMessage', {
          chat_id: chatId,
          text: `👑 Admin Control Panel\n\nTarget Admin ID: ${ADMIN_TELEGRAM_ID}\nStatus: Verified Active`,
          reply_markup: {
            inline_keyboard: [
              [
                {
                  text: 'Open Admin Dashboard 📊',
                  web_app: { url: appUrl },
                },
              ],
            ],
          },
        });
      } else {
        await callTelegramApi('sendMessage', {
          chat_id: chatId,
          text: `⚠️ Access Denied: Admin role required for /admin command.`,
        });
      }
    } else if (text === '/pending') {
      if (isAdminUser) {
        await callTelegramApi('sendMessage', {
          chat_id: chatId,
          text: `⏳ Pending Requests Queue\n\nOpen the WebApp Admin Dashboard to view clickable receipt screenshot thumbnails and process inline approvals.`,
          reply_markup: {
            inline_keyboard: [
              [
                {
                  text: 'Open Pending Queue in App 📊',
                  web_app: { url: appUrl },
                },
              ],
            ],
          },
        });
      } else {
        await callTelegramApi('sendMessage', {
          chat_id: chatId,
          text: `⚠️ Access Denied: Admin role required.`,
        });
      }
    } else if (text === '/stats') {
      if (isAdminUser) {
        await callTelegramApi('sendMessage', {
          chat_id: chatId,
          text: `📈 Yegna Bet Platform Stats\n\n- System Status: 24/7 Active\n- Games: Aviator, Virtual Sport, Keno, Coinflip, Mines, Dice, Color Wheel\n- Admin ID: ${ADMIN_TELEGRAM_ID}`,
          reply_markup: {
            inline_keyboard: [
              [
                {
                  text: 'Open Live Stats Dashboard 📊',
                  web_app: { url: appUrl },
                },
              ],
            ],
          },
        });
      } else {
        await callTelegramApi('sendMessage', {
          chat_id: chatId,
          text: `⚠️ Access Denied.`,
        });
      }
    }
  } else if (update.callback_query) {
    const cb = update.callback_query;
    const cbData = cb.data || '';
    const fromId = String(cb.from?.id || '');

    // Answer callback query to remove Telegram loading spinner
    await callTelegramApi('answerCallbackQuery', {
      callback_query_id: cb.id,
      text: 'Processing action...',
    });

    if (fromId === ADMIN_TELEGRAM_ID) {
      if (cbData.startsWith('approve_')) {
        const depositId = cbData.replace('approve_', '');
        await callTelegramApi('editMessageCaption', {
          chat_id: cb.message.chat.id,
          message_id: cb.message.message_id,
          caption: `${cb.message.caption || ''}\n\n✅ [APPROVED BY ADMIN]`,
        }).catch(() => {
          callTelegramApi('editMessageText', {
            chat_id: cb.message.chat.id,
            message_id: cb.message.message_id,
            text: `${cb.message.text || ''}\n\n✅ [APPROVED BY ADMIN]`,
          });
        });
      } else if (cbData.startsWith('reject_')) {
        const depositId = cbData.replace('reject_', '');
        await callTelegramApi('editMessageCaption', {
          chat_id: cb.message.chat.id,
          message_id: cb.message.message_id,
          caption: `${cb.message.caption || ''}\n\n❌ [REJECTED BY ADMIN]`,
        }).catch(() => {
          callTelegramApi('editMessageText', {
            chat_id: cb.message.chat.id,
            message_id: cb.message.message_id,
            text: `${cb.message.text || ''}\n\n❌ [REJECTED BY ADMIN]`,
          });
        });
      }
    }
  }
}

// API endpoint for receiving Telegram Webhook
app.post('/api/telegram-webhook', async (req, res) => {
  const appUrl = process.env.APP_URL || `http://${req.headers.host}`;
  await handleBotUpdate(req.body, appUrl);
  res.json({ ok: true });
});

// API endpoint for submitting deposit with screenshot receipt & SMS text proof
app.post('/api/deposit', upload.single('receipt'), async (req, res) => {
  try {
    const {
      userId,
      userPhone,
      sixDigitId,
      userDisplayName,
      telegramId,
      bankName,
      amount,
      proofType,
      smsText,
      imageData, // base64 fallback string if no multipart file
    } = req.body;

    const numAmount = parseFloat(amount || '0');
    const depositId = `DEP-${Date.now()}`;

    // Notify Target Admin 8488592165 via Telegram Bot API
    let captionDetails = 
`📥 *NEW DEPOSIT REQUEST*
--------------------------------
👤 *Player*: ${userDisplayName || 'Player'}
🆔 *ID*: \`${sixDigitId || 'YG-GUEST'}\`
📱 *Phone/TG*: ${userPhone || telegramId || 'N/A'}
🏦 *Bank*: *${bankName || 'Telebirr'}*
💰 *Amount*: *${numAmount.toFixed(2)} ETB*
📄 *Proof Type*: *${proofType === 'sms' ? '📝 SMS Confirmation Text' : '📷 Screenshot Image'}*`;

    if (smsText && smsText.trim()) {
      captionDetails += `\n💬 *SMS Confirmation Proof*:
\`\`\`
${smsText.trim()}
\`\`\``;
    }

    captionDetails += `\n--------------------------------\nDeposit ID: \`${depositId}\``;

    const inlineKeyboard = [
      [
        { text: 'Approve ✅', callback_data: `approve_dep_${depositId}` },
        { text: 'Reject ❌', callback_data: `reject_dep_${depositId}` },
      ],
    ];

    let telegramResult;

    // Send Photo if image file or base64 provided
    if (req.file) {
      const formData = new FormData();
      formData.append('chat_id', ADMIN_TELEGRAM_ID);
      formData.append('caption', captionDetails);
      formData.append('parse_mode', 'Markdown');
      formData.append('reply_markup', JSON.stringify({ inline_keyboard: inlineKeyboard }));
      
      const blob = new Blob([req.file.buffer], { type: req.file.mimetype });
      formData.append('photo', blob, req.file.originalname || 'receipt.jpg');

      telegramResult = await callTelegramApi('sendPhoto', formData, true);
    } else if (imageData && imageData.startsWith('data:image')) {
      telegramResult = await callTelegramApi('sendMessage', {
        chat_id: ADMIN_TELEGRAM_ID,
        text: `${captionDetails}\n\n🖼️ [Receipt Screenshot Attached in WebApp]`,
        parse_mode: 'Markdown',
        reply_markup: { inline_keyboard: inlineKeyboard },
      });
    } else {
      telegramResult = await callTelegramApi('sendMessage', {
        chat_id: ADMIN_TELEGRAM_ID,
        text: captionDetails,
        parse_mode: 'Markdown',
        reply_markup: { inline_keyboard: inlineKeyboard },
      });
    }

    res.json({
      success: true,
      depositId,
      telegramNotified: telegramResult?.ok || false,
    });
  } catch (err: any) {
    console.error('Error submitting deposit via server:', err);
    res.status(500).json({ success: false, error: err.message || 'Server error' });
  }
});

// API endpoint for submitting withdrawal request to Admin ID 8488592165
app.post('/api/withdraw', async (req, res) => {
  try {
    const {
      withdrawId,
      userId,
      sixDigitId,
      userDisplayName,
      playerTelegramId,
      bankName,
      amount,
      accountNumber,
      accountName,
    } = req.body;

    const numAmount = parseFloat(amount || '0');
    const idStr = withdrawId || `WD-${Date.now()}`;

    const textDetails = 
`💸 *NEW WITHDRAWAL REQUEST*
--------------------------------
👤 *Player*: ${userDisplayName || 'Player'}
🆔 *ID*: \`${sixDigitId || 'YG-GUEST'}\`
📱 *TG ID*: ${playerTelegramId || 'N/A'}
🏦 *Payout Bank*: *${bankName || 'Telebirr'}*
💰 *Payout Amount*: *${numAmount.toFixed(2)} ETB*
🔒 *Pre-Registered Locked Account*: \`${accountNumber || 'N/A'}\`
👤 *Account Holder Name*: *${accountName || 'N/A'}*
--------------------------------
Withdrawal ID: \`${idStr}\``;

    const inlineKeyboard = [
      [
        { text: 'Approve Payout ✅', callback_data: `approve_wd_${idStr}` },
        { text: 'Reject & Refund ❌', callback_data: `reject_wd_${idStr}` },
      ],
    ];

    const result = await callTelegramApi('sendMessage', {
      chat_id: ADMIN_TELEGRAM_ID,
      text: textDetails,
      parse_mode: 'Markdown',
      reply_markup: { inline_keyboard: inlineKeyboard },
    });

    res.json({ success: true, withdrawId: idStr, telegramNotified: result?.ok || false });
  } catch (err: any) {
    console.error('Error submitting withdrawal via server:', err);
    res.status(500).json({ success: false, error: err.message || 'Server error' });
  }
});

// API endpoint for notifying player on approval/rejection
app.post('/api/notify-player', async (req, res) => {
  const { playerTelegramId, message, type } = req.body;
  if (playerTelegramId) {
    await callTelegramApi('sendMessage', {
      chat_id: playerTelegramId,
      text: message,
    });
  }
  res.json({ ok: true });
});

// API endpoint for server-side game outcome calculation with Cryptographically Secure RNG
app.post('/api/game/play', async (req, res) => {
  try {
    const { userId, gameType, betAmount, clientSeed, params } = req.body;

    const numBet = parseFloat(betAmount || '0');
    if (isNaN(numBet) || numBet <= 0) {
      return res.status(400).json({ success: false, error: 'Invalid bet amount.' });
    }

    const serverSeed = generateSecureServerSeed();
    const serverSeedHashStr = hashServerSeed(serverSeed);
    const cSeed = clientSeed || crypto.randomBytes(8).toString('hex');
    const nonce = params?.nonce || 1;

    let resultData: any = {};
    let won = false;
    let multiplier = 0;
    let payout = 0;

    switch (gameType) {
      case 'aviator': {
        const crash = calculateAviatorCrash(serverSeed, cSeed, nonce);
        const autoCashout = parseFloat(params?.autoCashout || '0');
        multiplier = crash;
        resultData = { crashMultiplier: crash };
        if (autoCashout > 1.00 && crash >= autoCashout) {
          won = true;
          payout = Math.floor(numBet * autoCashout * 100) / 100;
        }
        break;
      }

      case 'keno': {
        const drawn = calculateKenoDraw(serverSeed, cSeed, nonce);
        const selected: number[] = params?.selectedNumbers || [];
        const hits = selected.filter((n) => drawn.includes(n));
        const hitCount = hits.length;
        
        // Keno Multiplier Table based on selected count and hits
        const kenoPayoutMap: Record<number, Record<number, number>> = {
          1: { 1: 3.5 },
          2: { 1: 1.0, 2: 7.0 },
          3: { 2: 2.5, 3: 16.0 },
          4: { 2: 1.5, 3: 5.0, 4: 40.0 },
          5: { 3: 3.0, 4: 15.0, 5: 100.0 },
          6: { 3: 1.8, 4: 8.0, 5: 50.0, 6: 250.0 },
          7: { 4: 4.0, 5: 20.0, 6: 100.0, 7: 500.0 },
          8: { 4: 2.0, 5: 10.0, 6: 50.0, 7: 200.0, 8: 1000.0 },
          9: { 5: 5.0, 6: 25.0, 7: 150.0, 8: 500.0, 9: 2000.0 },
          10: { 5: 2.0, 6: 10.0, 7: 50.0, 8: 250.0, 9: 1000.0, 10: 5000.0 },
        };

        const selCount = selected.length;
        multiplier = kenoPayoutMap[selCount]?.[hitCount] || 0;
        won = multiplier > 0;
        payout = Math.floor(numBet * multiplier * 100) / 100;
        resultData = { drawnNumbers: drawn, hits, hitCount };
        break;
      }

      case 'dice': {
        const roll = calculateDiceRoll(serverSeed, cSeed, nonce);
        const target = parseFloat(params?.targetRoll || '50');
        const rollUnder = Boolean(params?.rollUnder ?? true);

        if (rollUnder) {
          won = roll < target;
          const winProb = target / 100;
          multiplier = Math.floor(((1 - 0.03) / winProb) * 100) / 100;
        } else {
          won = roll > target;
          const winProb = (100 - target) / 100;
          multiplier = Math.floor(((1 - 0.03) / winProb) * 100) / 100;
        }

        if (won) {
          payout = Math.floor(numBet * multiplier * 100) / 100;
        }
        resultData = { roll, target, rollUnder };
        break;
      }

      case 'coinflip': {
        const outcome = calculateCoinflip(serverSeed, cSeed, nonce);
        const choice = params?.choice || 'HEADS';
        won = outcome === choice;
        multiplier = won ? 1.96 : 0;
        payout = won ? Math.floor(numBet * 1.96 * 100) / 100 : 0;
        resultData = { outcome, choice };
        break;
      }

      case 'mines': {
        const mineCount = parseInt(params?.mineCount || '3');
        const grid = calculateMinesGrid(serverSeed, cSeed, nonce, mineCount);
        resultData = { grid, mineCount };
        won = true; // Initialized grid
        break;
      }

      case 'colorwheel': {
        const { index, multiplier: spinMult } = calculateColorWheel(serverSeed, cSeed, nonce);
        multiplier = spinMult;
        won = multiplier > 0;
        payout = Math.floor(numBet * multiplier * 100) / 100;
        resultData = { segmentIndex: index, multiplier: spinMult };
        break;
      }

      default:
        return res.status(400).json({ success: false, error: 'Unsupported game type.' });
    }

    res.json({
      success: true,
      gameType,
      betAmount: numBet,
      won,
      multiplier,
      payout,
      outcome: resultData,
      serverSeed,
      serverSeedHash: serverSeedHashStr,
      clientSeed: cSeed,
      nonce,
      timestamp: new Date().toISOString(),
    });
  } catch (err: any) {
    console.error('Error executing server-side game calculation:', err);
    res.status(500).json({ success: false, error: err.message || 'Server-side game calculation failed.' });
  }
});

// Health check route
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    adminTelegramId: ADMIN_TELEGRAM_ID,
    botActive: Boolean(TELEGRAM_BOT_TOKEN),
    timestamp: new Date().toISOString(),
  });
});

// Setup Vite or Static File Serving
async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    // ማስተካከያ የተደረገበት መስመር ( '*' ወደ '/*' ተቀይሯል )
    app.get('/*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(Number(PORT), '0.0.0.0', () => {
    console.log(`🚀 Yegna Bet Server running on http://0.0.0.0:${PORT}`);
    console.log(`👑 Target Admin Telegram ID: ${ADMIN_TELEGRAM_ID}`);
  });
}

startServer();
