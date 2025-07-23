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
// Status helper
//-------------------------------------------------------------
function status(msg) {
  document.getElementById('statusBar').textContent = `${new Date().toLocaleTimeString()}: ${msg}`;
}

//-------------------------------------------------------------
// Connect to Binance – sets activeClientId
//-------------------------------------------------------------
async function connect() {
  status('Connecting to Binance API...');
  const data = await api('/api/connect', 'POST');
  if (data.success) {
    activeClientId = data.client_id; // "live_client"
    document.getElementById('status').innerHTML = '<strong style="color: #3fb950;">✅ Connected (LIVE)</strong>';
    document.getElementById('configDebug').style.display = 'none';
    refreshAll();
    status('Connected to Binance LIVE API - All data loading...');
  } else {
    document.getElementById('status').innerHTML = `<strong style="color: var(--color-5);">❌ Connection Failed</strong>`;
    if (data.error && data.error.includes('credentials')) {
      document.getElementById('status').innerHTML += '<br><small>Click "🔧 Check Config" to verify your API keys</small>';
    }
    status('Connection failed: ' + (data.error || 'Unknown error'));
  }
}

//-------------------------------------------------------------
// Config check
//-------------------------------------------------------------
async function checkConfig() {
  status('Checking API configuration...');
  const data = await api('/api/debug/config');
  
  document.getElementById('configDebug').innerHTML = `
    <h5 style="color: var(--color-1); margin-bottom: 10px;">🔧 API Configuration Status</h5>
    
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
      <div>
        <h6 style="color: #58a6ff;">API Key:</h6>
        <p>Set: <span style="color: ${data.binance_api_key_set ? '#3fb950' : 'var(--color-5)'};">${data.binance_api_key_set ? 'YES' : 'NO'}</span></p>
        <p>Length: ${data.api_key_length} chars</p>
        <p>Preview: <code>${data.api_key_preview}</code></p>
      </div>
      
      <div>
        <h6 style="color: #58a6ff;">Secret Key:</h6>
        <p>Set: <span style="color: ${data.binance_secret_key_set ? '#3fb950' : 'var(--color-5)'};">${data.binance_secret_key_set ? 'YES' : 'NO'}</span></p>
        <p>Length: ${data.secret_key_length} chars</p>
        <p>Preview: <code>${data.secret_key_preview}</code></p>
      </div>
    </div>
    
    <div style="margin-top: 10px;">
      <h6 style="color: #58a6ff;">Environment Variables:</h6>
      <p>BINANCE_API_KEY in env: <span style="color: ${data.env_vars_available.BINANCE_API_KEY ? '#3fb950' : 'var(--color-5)'};">${data.env_vars_available.BINANCE_API_KEY ? 'YES' : 'NO'}</span></p>
      <p>BINANCE_SECRET_KEY in env: <span style="color: ${data.env_vars_available.BINANCE_SECRET_KEY ? '#3fb950' : 'var(--color-5)'};">${data.env_vars_available.BINANCE_SECRET_KEY ? 'YES' : 'NO'}</span></p>
    </div>
    
    ${!data.binance_api_key_set || !data.binance_secret_key_set ? `
    <div style="margin-top: 15px; padding: 10px; background: rgba(150, 44, 47, 0.1); border: 1px solid var(--color-5); border-radius: 4px;">
      <h6 style="color: var(--color-5);">❌ Configuration Issue!</h6>
      <p style="font-size: 0.8em;">Your Binance API credentials are not properly set. Please add them to your Railway environment variables:</p>
      <p style="font-size: 0.8em;">1. Go to Railway Dashboard → Your App → Variables</p>
      <p style="font-size: 0.8em;">2. Add: BINANCE_API_KEY = your_api_key</p>
      <p style="font-size: 0.8em;">3. Add: BINANCE_SECRET_KEY = your_secret_key</p>
      <p style="font-size: 0.8em;">4. Redeploy the application</p>
    </div>
    ` : `
    <div style="margin-top: 15px; padding: 10px; background: rgba(36, 76, 72, 0.1); border: 1px solid var(--color-1); border-radius: 4px;">
      <h6 style="color: var(--color-1);">✅ Configuration Looks Good!</h6>
      <p style="font-size: 0.8em;">Your API credentials appear to be properly configured. Try connecting to Binance API.</p>
    </div>
    `}
  `;
  document.getElementById('configDebug').style.display = 'block';
  
  if (data.binance_api_key_set && data.binance_secret_key_set) {
    status('API configuration looks good - try connecting');
  } else {
    status('API configuration issue - check Railway environment variables');
  }
}

//-------------------------------------------------------------
// Format helpers for better display
//-------------------------------------------------------------
const formatAPY = (apy) => {
  const apyValue = parseFloat(apy) || 0;
  if (apyValue === 0) {
    return '<span style="color: #8b949e; font-weight: normal;">0.00%</span>';
  }
  return `<span style="color: #244c48; font-weight: bold;">${apyValue.toFixed(2)}%</span>`;
};

const formatAmount = (amount) => {
  const amtValue = parseFloat(amount) || 0;
  return `<span style="color: #58a6ff; font-weight: bold;">${amtValue.toFixed(4)}</span>`;
};

const formatDailyRewards = (rewards) => {
  const rewardValue = parseFloat(rewards) || 0;
  return `<span style="color: #9c4d30; font-weight: bold;">$${rewardValue.toFixed(4)}</span>`;
};

//-------------------------------------------------------------
// UI refresh helpers use activeClientId
//-------------------------------------------------------------
async function refreshBalance() {
  if (!activeClientId) return;
  const bal = await api(`/api/balance/${activeClientId}`);
  if (bal.error) return console.warn(bal.error);
  
  const s = bal.account_summary;
  document.getElementById('wallet-balance').innerHTML = `
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px;">
      <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
        <div style="font-size: 1.5em; font-weight: bold; color: #58a6ff;">$${s.total_wallet_balance.toFixed(2)}</div>
        <div style="font-size: 0.8em; color: #8b949e;">Total</div>
      </div>
      <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
        <div style="font-size: 1.5em; font-weight: bold; color: #58a6ff;">$${s.available_balance.toFixed(2)}</div>
        <div style="font-size: 0.8em; color: #8b949e;">Available</div>
      </div>
      <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
        <div style="font-size: 1.5em; font-weight: bold; color: ${s.total_unrealized_pnl >= 0 ? '#244c48' : '#962c2f'};">$${s.total_unrealized_pnl.toFixed(2)}</div>
        <div style="font-size: 0.8em; color: #8b949e;">P&L</div>
      </div>
    </div>
  `;
}

async function refreshPositions() {
  if (!activeClientId) return;
  const pos = await api(`/api/positions/${activeClientId}`);
  if (pos.error) return console.warn(pos.error);
  
  if (!pos.positions || pos.positions.length === 0) {
    document.getElementById('positions-list').innerHTML = '<p style="color: #8b949e;">No open futures positions</p>';
    return;
  }
  
  document.getElementById('positions-list').innerHTML = pos.positions.map(p => `
    <div style="background: #0d1117; padding: 12px; margin: 8px 0; border-radius: 6px; border: 1px solid #30363d;">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <strong style="color: #f0f6fc;">${p.symbol} ${p.position_side}</strong>
        <span style="color: ${p.unrealized_pnl >= 0 ? '#244c48' : '#962c2f'}; font-weight: bold;">$${p.unrealized_pnl.toFixed(2)}</span>
      </div>
      <div style="font-size: 0.9em; color: #8b949e; margin-top: 5px;">
        Amount: ${p.position_amount} | Entry: $${p.entry_price.toFixed(4)}
        ${p.mark_price ? ` | Mark: $${p.mark_price.toFixed(4)}` : ''}
      </div>
    </div>
  `).join('');
}

async function refreshEarn() {
  if (!activeClientId) return;
  const earn = await api(`/api/earn/${activeClientId}`);
  if (earn.error) return console.warn(earn.error);
  
  if (earn.success && earn.summary && earn.summary.total_positions > 0) {
    const summary = earn.summary;
    const positions = earn.earn_positions || [];
    
    // Update summary
    document.getElementById('earn-summary').innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-bottom: 15px;">
        <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
          <div style="font-size: 1.3em; font-weight: bold; color: #58a6ff;">$${summary.total_earn_balance.toFixed(2)}</div>
          <div style="font-size: 0.8em; color: #8b949e;">Total Earn</div>
        </div>
        <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
          <div style="font-size: 1.3em; font-weight: bold; color: #9c4d30;">$${summary.daily_rewards.toFixed(4)}</div>
          <div style="font-size: 0.8em; color: #8b949e;">Daily Rewards</div>
        </div>
        <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
          <div style="font-size: 1.3em; font-weight: bold; color: #244c48;">${summary.flexible_count}</div>
          <div style="font-size: 0.8em; color: #8b949e;">Flexible</div>
        </div>
        <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
          <div style="font-size: 1.3em; font-weight: bold; color: #962c2f;">${summary.locked_count}</div>
          <div style="font-size: 0.8em; color: #8b949e;">Locked</div>
        </div>
      </div>
    `;
    
    // Display positions with improved formatting
    if (positions.length > 0) {
      document.getElementById('earn-positions').innerHTML = positions.map(pos => `
        <div style="background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 12px; margin: 8px 0;">
          <div style="margin-bottom: 8px;">
            <span style="display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.7em; font-weight: 500; margin-right: 8px; background: ${pos.type === 'flexible' ? 'rgba(36, 76, 72, 0.2)' : 'rgba(150, 44, 47, 0.2)'}; color: ${pos.type === 'flexible' ? '#244c48' : '#962c2f'};">
              ${pos.type.toUpperCase()}
            </span>
            <span style="color: #58a6ff; font-weight: bold;">${pos.asset}</span>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; font-size: 0.85em;">
            <span>Amount: ${formatAmount(pos.amount)}</span>
            <span>APY: ${formatAPY(pos.apy)}</span>
            <span>Daily: ${formatDailyRewards(pos.daily_rewards)}</span>
            ${pos.type === 'locked' && pos.duration ? `<span>Duration: <strong>${pos.duration} days</strong></span>` : ''}
            ${pos.type === 'flexible' && pos.can_redeem !== undefined ? `<span>Redeemable: <strong>${pos.can_redeem ? 'Yes' : 'No'}</strong></span>` : ''}
            ${pos.yesterday_rewards !== undefined && pos.yesterday_rewards > 0 ? `<span>Yesterday: ${formatDailyRewards(pos.yesterday_rewards)}</span>` : ''}
          </div>
        </div>
      `).join('');
    } else {
      document.getElementById('earn-positions').innerHTML = '<p style="color: #8b949e;">💎 Earn positions summary loaded, but no detailed positions available</p>';
    }
  } else {
    document.getElementById('earn-summary').innerHTML = '<p style="color: #8b949e;">💎 No earn positions found</p>';
    document.getElementById('earn-positions').innerHTML = '';
  }
}

async function refreshTracked() {
  const data = await api('/api/tracked-positions');
  if (data.success && data.tracked_positions.length) {
    document.getElementById('trackedPositions').innerHTML = data.tracked_positions.map(p => `
      <div class="item">
        <strong>${p.symbol} ${p.side}</strong>
        <small>Strategy: ${p.strategy_id} | Qty: ${p.quantity} | Entry: $${p.entry_price.toFixed(4)} | Age: ${p.age_minutes}m</small>
      </div>`).join('');
  } else {
    document.getElementById('trackedPositions').innerHTML = '<p>No tracked positions</p>';
  }
  document.getElementById('tracked').textContent = data.total_positions || 0;
}

async function loadStrategies() {
  const strategies = await api('/api/strategies');
  document.getElementById('strategies').textContent = strategies.length;
  document.getElementById('signals').textContent = strategies.reduce((sum, s) => sum + s.total_signals, 0);
  
  document.getElementById('strategiesList').innerHTML = strategies.length ? strategies.map(s => `
    <div class="item">
      <h4>${s.name}</h4>
      <p>${s.description || 'No description'}</p>
      <small>ID: ${s.id} | Signals: ${s.total_signals}</small>
      <div style="margin-top: 10px;">
        <code style="font-size: 0.7em; word-break: break-all;">${location.origin}/webhook/tradingview/strategy/${s.id}</code>
        <button class="btn" onclick="copyURL(${s.id})" style="font-size: 12px; padding: 4px 8px; margin-top: 5px;">📋 Copy</button>
      </div>
    </div>`).join('') : '<p>No strategies yet</p>';
}

async function createStrategy() {
  const name = document.getElementById('strategyName').value;
  if (!name) return status('Enter strategy name');
  
  const result = await api('/api/strategies', {
    method: 'POST',
    body: JSON.stringify({ name, description: document.getElementById('strategyDesc').value })
  });
  
  if (result.success) {
    document.getElementById('strategyName').value = '';
    document.getElementById('strategyDesc').value = '';
    loadStrategies();
    status(`Strategy "${name}" created! ID: ${result.strategy_id}`);
  } else {
    status('Error: ' + result.error);
  }
}

async function refreshWebhooks() {
  const webhookData = await api('/api/webhooks/activity');
  document.getElementById('totalWebhooks').textContent = webhookData.length;
  document.getElementById('lastWebhook').textContent = webhookData.length ? new Date(webhookData[0].timestamp).toLocaleTimeString() : 'Never';
  
  // Live feed
  document.getElementById('liveFeed').innerHTML = webhookData.slice(0, 5).map(w => `
    <div class="feed-item">
      <strong>${new Date(w.timestamp).toLocaleTimeString()} - ${w.strategy_name}</strong>
      <div style="font-size: 0.8em;">Action: ${w.parsed_data.action} | Symbol: ${w.parsed_data.symbol} | Price: $${w.parsed_data.price}</div>
    </div>`).join('') || '<p>No recent activity</p>';
  
  // Activity list
  document.getElementById('activityList').innerHTML = webhookData.slice(0, 10).map(w => `
    <div class="alert alert-success" style="margin: 5px 0; padding: 8px;">
      <strong>${w.strategy_name}</strong> - ${new Date(w.timestamp).toLocaleString()}<br>
      <small>Action: ${w.parsed_data.action} | Symbol: ${w.parsed_data.symbol} | Qty: ${w.parsed_data.quantity} | Price: $${w.parsed_data.price}</small>
    </div>`).join('') || '<p>No webhook activity</p>';
}

async function testParsing() {
  const message = document.getElementById('testMessage').value;
  if (!message) return status('Enter test message');
  
  const result = await api('/webhook/debug-parse', {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain' },
    body: message
  });
  
  document.getElementById('parseResult').innerHTML = `
    <div class="help" style="margin-top: 10px;">
      <h5>🔍 Parsing Results</h5>
      <p><strong>Action:</strong> ${result.parsed_result.action}</p>
      <p><strong>Symbol:</strong> ${result.parsed_result.symbol}</p>
      <p><strong>Quantity:</strong> ${result.parsed_result.quantity}</p>
      <p><strong>Price:</strong> Will fetch from Binance API</p>
    </div>`;
}

function refreshAll() {
  if (activeClientId) {
    refreshBalance();
    refreshPositions();
    refreshEarn();
  }
  refreshTracked();
}