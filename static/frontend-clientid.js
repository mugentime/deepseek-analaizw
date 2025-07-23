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
    document.getElementById('status').innerHTML = '<strong style="color: #244c48;">✅ Connected (LIVE)</strong>';
    refreshAll();
  } else {
    alert('Failed to connect: ' + (data.error || 'Unknown error'));
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
  const tracked = await api('/api/tracked-positions');
  if (tracked.error) return console.warn(tracked.error);
  
  if (!tracked.tracked_positions || tracked.tracked_positions.length === 0) {
    document.getElementById('trackedPositions').innerHTML = '<p style="color: #8b949e;">No tracked positions</p>';
    return;
  }
  
  document.getElementById('trackedPositions').innerHTML = tracked.tracked_positions.map(pos => `
    <div style="background: #0d1117; padding: 12px; margin: 8px 0; border-radius: 6px; border: 1px solid #30363d;">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <strong style="color: #f0f6fc;">${pos.symbol} ${pos.side}</strong>
        <span style="color: #8b949e; font-size: 0.8em;">${pos.age_minutes}m ago</span>
      </div>
      <div style="font-size: 0.9em; color: #8b949e; margin-top: 5px;">
        Qty: ${pos.quantity} | Entry: $${pos.entry_price.toFixed(4)} | Strategy: ${pos.strategy_id}
      </div>
    </div>
  `).join('');
}

async function loadStrategies() {
  const data = await api('/api/strategies');
  const count = data.length;
  document.getElementById('strategies').textContent = count;
  
  if (count === 0) {
    document.getElementById('strategiesList').innerHTML = '<p style="color: #8b949e;">No strategies created yet</p>';
    return;
  }
  
  document.getElementById('strategiesList').innerHTML = data.map(s => `
    <div style="background: #0d1117; padding: 12px; margin: 8px 0; border-radius: 6px; border: 1px solid #30363d;">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <strong style="color: #f0f6fc;">${s.name}</strong>
        <span style="color: #244c48; font-weight: bold;">${s.total_signals} signals</span>
      </div>
      <div style="font-size: 0.9em; color: #8b949e; margin: 5px 0;">${s.description || 'No description'}</div>
      <div style="font-size: 0.8em; color: #8b949e;">ID: ${s.id} | Created: ${new Date(s.created_at).toLocaleDateString()}</div>
      <button onclick="copyURL(${s.id})" style="background: #244c48; color: white; border: none; padding: 4px 8px; border-radius: 4px; margin-top: 5px; cursor: pointer;">Copy URL</button>
    </div>
  `).join('');
}

async function createStrategy() {
  const name = document.getElementById('strategyName').value.trim();
  const description = document.getElementById('strategyDesc').value.trim();
  
  if (!name) {
    alert('Please enter a strategy name');
    return;
  }
  
  const data = await api('/api/strategies', 'POST', {name, description});
  if (data.success) {
    status(`Strategy "${name}" created with ID ${data.strategy_id}`);
    document.getElementById('strategyName').value = '';
    document.getElementById('strategyDesc').value = '';
    loadStrategies();
  } else {
    alert('Failed to create strategy: ' + data.error);
  }
}

async function refreshWebhooks() {
  const data = await api('/api/webhooks/activity');
  const count = data.length;
  
  // Update stats
  document.getElementById('totalWebhooks').textContent = count;
  document.getElementById('successTrades').textContent = data.filter(w => w.parsed_data?.action !== 'error').length;
  document.getElementById('failedWebhooks').textContent = data.filter(w => w.parsed_data?.action === 'error').length;
  document.getElementById('lastWebhook').textContent = count > 0 ? new Date(data[0].timestamp).toLocaleTimeString() : 'Never';
  
  // Live feed (last 5)
  const recent = data.slice(0, 5);
  document.getElementById('liveFeed').innerHTML = recent.length > 0 ? recent.map(w => `
    <div class="feed-item">
      <strong>${w.parsed_data.action.toUpperCase()}</strong> ${w.parsed_data.symbol} 
      <span style="float: right; color: #8b949e;">${new Date(w.timestamp).toLocaleTimeString()}</span>
    </div>
  `).join('') : '<p style="color: #8b949e;">Waiting for signals...</p>';
  
  // Activity list (all)
  document.getElementById('activityList').innerHTML = data.length > 0 ? data.map(w => `
    <div style="background: #0d1117; padding: 10px; margin: 5px 0; border-radius: 4px; border: 1px solid #30363d;">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <strong style="color: #f0f6fc;">${w.strategy_name}</strong>
        <span style="color: #8b949e; font-size: 0.8em;">${new Date(w.timestamp).toLocaleString()}</span>
      </div>
      <div style="font-size: 0.9em; color: #8b949e; margin: 5px 0;">
        <strong>${w.parsed_data.action.toUpperCase()}</strong> ${w.parsed_data.symbol} 
        ${w.parsed_data.quantity > 0 ? `Qty: ${w.parsed_data.quantity}` : ''} 
        ${w.parsed_data.price > 0 ? `Price: $${w.parsed_data.price.toFixed(4)}` : ''}
      </div>
      <div style="font-size: 0.8em; color: #8b949e; font-family: monospace;">${w.raw_message}</div>
    </div>
  `).join('') : '<p style="color: #8b949e;">No webhook activity yet</p>';
}

async function testParsing() {
  const message = document.getElementById('testMessage').value.trim();
  if (!message) {
    alert('Please enter a test message');
    return;
  }
  
  const data = await api('/webhook/debug-parse', 'POST', null);
  
  // Need to send as raw text, not JSON
  try {
    const response = await fetch('/webhook/debug-parse', {
      method: 'POST',
      headers: {'Content-Type': 'text/plain'},
      body: message
    });
    const result = await response.json();
    
    document.getElementById('parseResult').innerHTML = `
      <div style="background: #0d1117; padding: 10px; border-radius: 6px; margin-top: 10px;">
        <h5 style="color: #244c48; margin-bottom: 8px;">Parse Result:</h5>
        <pre style="color: #8b949e; font-size: 0.9em;">${JSON.stringify(result, null, 2)}</pre>
      </div>
    `;
  } catch (err) {
    document.getElementById('parseResult').innerHTML = `<p style="color: #962c2f;">Error: ${err.message}</p>`;
  }
}

async function checkConfig() {
  const config = await api('/api/debug/config');
  document.getElementById('configDebug').style.display = 'block';
  document.getElementById('configDebug').innerHTML = `
    <h5 style="color: #244c48; margin-bottom: 8px;">API Configuration:</h5>
    <pre style="color: #8b949e; font-size: 0.8em;">${JSON.stringify(config, null, 2)}</pre>
  `;
}

function status(message) {
  document.getElementById('statusBar').textContent = message;
  setTimeout(() => {
    document.getElementById('statusBar').textContent = 'Efficient Trading Platform - Ready';
  }, 3000);
}

function copyURL(id) {
  const url = `${location.origin}/webhook/tradingview/strategy/${id}`;
  navigator.clipboard.writeText(url);
  status(`Webhook URL copied for strategy ${id}!`);
}

function refreshAll() {
  refreshBalance();
  refreshPositions();
  refreshEarn();
  refreshTracked();
}