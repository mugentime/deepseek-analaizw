// ------------------------------------------------------------
// Global state for active client ID
// ------------------------------------------------------------
let activeClientId = null;

//-------------------------------------------------------------
// Generic helper to call the backend
//-------------------------------------------------------------
async function api(url, method = 'GET', body = null) {
  try {
    const res = await fetch(url, {
      method,
      headers: {'Content-Type': 'application/json'},
      body: body ? JSON.stringify(body) : null
    });
    return await res.json();
  } catch (err) {
    console.error('API error', err);
    return {success: false, error: err.message};
  }
}

//-------------------------------------------------------------
// Connect to Binance – sets activeClientId
//-------------------------------------------------------------
async function connect() {
  const data = await api('/api/connect', 'POST');
  if (data.success) {
    activeClientId = data.client_id; // "live_client"
    document.getElementById('status').textContent = 'Connected ✅';
    refreshAll();
  } else {
    alert('Failed to connect: ' + (data.error || 'Unknown error'));
  }
}

//-------------------------------------------------------------
// UI refresh helpers use activeClientId
//-------------------------------------------------------------
async function refreshBalance() {
  if (!activeClientId) return;
  const bal = await api(`/api/balance/${activeClientId}`);
  if (bal.error) return console.warn(bal.error);
  document.getElementById('wallet-balance').textContent =
    `$${bal.account_summary?.total_wallet_balance ?? 0}`;
}

async function refreshPositions() {
  if (!activeClientId) return;
  const pos = await api(`/api/positions/${activeClientId}`);
  if (pos.error) return console.warn(pos.error);
  // render positions...
}

async function refreshEarn() {
  if (!activeClientId) return;
  const earn = await api(`/api/earn/${activeClientId}`);
  if (earn.error) return console.warn(earn.error);
  // render earn placeholder...
}

function refreshAll() {
  refreshBalance();
  refreshPositions();
  refreshEarn();
}
