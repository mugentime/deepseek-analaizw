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
    document.getElementById('status').innerHTML = '<strong style="color: #3fb950;">✅ Connected (LIVE)</strong>';
    refreshAll();
  } else {
    alert('Failed to connect: ' + (data.error || 'Unknown error'));
  }
}

//-------------------------------------------------------------
// Status bar helper
//-------------------------------------------------------------
function status(message) {
  const statusBar = document.getElementById('statusBar');
  if (statusBar) {
    statusBar.textContent = message;
    statusBar.style.background = 'var(--color-1)';
    setTimeout(() => {
      statusBar.style.background = 'var(--color-3)';
    }, 3000);
  }
}

//-------------------------------------------------------------
// Check API configuration
//-------------------------------------------------------------
async function checkConfig() {
  const config = await api('/api/debug/config');
  const configDiv = document.getElementById('configDebug');
  
  configDiv.innerHTML = `
    <h5>🔧 API Configuration Debug</h5>
    <p><strong>API Key Set:</strong> ${config.binance_api_key_set ? '✅' : '❌'}</p>
    <p><strong>Secret Key Set:</strong> ${config.binance_secret_key_set ? '✅' : '❌'}</p>
    <p><strong>API Key Length:</strong> ${config.api_key_length}</p>
    <p><strong>Secret Key Length:</strong> ${config.secret_key_length}</p>
    <p><strong>API Key Preview:</strong> ${config.api_key_preview}</p>
    <p><strong>Secret Key Preview:</strong> ${config.secret_key_preview}</p>
    <div style="margin-top: 10px;">
      <strong>Environment Variables:</strong><br>
      BINANCE_API_KEY: ${config.env_vars_available.BINANCE_API_KEY ? '✅' : '❌'}<br>
      BINANCE_SECRET_KEY: ${config.env_vars_available.BINANCE_SECRET_KEY ? '✅' : '❌'}
    </div>
  `;
  
  configDiv.style.display = configDiv.style.display === 'none' ? 'block' : 'none';
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
  if (data.error) return console.warn(data.error);
  
  const positions = data.tracked_positions || [];
  document.getElementById('tracked').textContent = positions.length;
  
  if (positions.length === 0) {
    document.getElementById('trackedPositions').innerHTML = '<p style="color: #8b949e;">No tracked positions</p>';
    return;
  }
  
  document.getElementById('trackedPositions').innerHTML = positions.map(pos => `
    <div style="background: #0d1117; padding: 10px; margin: 8px 0; border-radius: 6px; border: 1px solid #30363d;">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <strong style="color: #f0f6fc;">${pos.symbol} ${pos.side}</strong>
        <span style="color: #8b949e; font-size: 0.9em;">${pos.age_minutes}m ago</span>
      </div>
      <div style="font-size: 0.9em; color: #8b949e; margin-top: 5px;">
        Qty: ${pos.quantity} | Entry: $${pos.entry_price.toFixed(4)} | Strategy: ${pos.strategy_id}
      </div>
    </div>
  `).join('');
}

async function loadStrategies() {
  const data = await api('/api/strategies');
  const strategies = Array.isArray(data) ? data : [];
  
  document.getElementById('strategies').textContent = strategies.length;
  
  if (strategies.length === 0) {
    document.getElementById('strategiesList').innerHTML = '<p style="color: #8b949e;">No strategies created yet</p>';
    return;
  }
  
  document.getElementById('strategiesList').innerHTML = strategies.map(strategy => `
    <div style="background: #0d1117; padding: 12px; margin: 8px 0; border-radius: 6px; border: 1px solid #30363d;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <strong style="color: #f0f6fc;">${strategy.name}</strong>
        <span style="color: #244c48; font-weight: bold;">${strategy.total_signals} signals</span>
      </div>
      <p style="color: #8b949e; font-size: 0.9em; margin-bottom: 8px;">${strategy.description || 'No description'}</p>
      <div style="font-family: monospace; font-size: 0.8em; color: #58a6ff; background: #21262d; padding: 8px; border-radius: 4px; word-break: break-all;">
        ${location.origin}/webhook/tradingview/strategy/${strategy.id}
      </div>
      <button class="btn" onclick="copyURL(${strategy.id})" style="margin-top: 8px; font-size: 0.8em;">📋 Copy URL</button>
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
  
  const data = await api('/api/strategies', 'POST', {
    name: name,
    description: description
  });
  
  if (data.success) {
    status(`Strategy "${name}" created with ID ${data.strategy_id}`);
    document.getElementById('strategyName').value = '';
    document.getElementById('strategyDesc').value = '';
    loadStrategies();
  } else {
    alert('Failed to create strategy: ' + (data.error || 'Unknown error'));
  }
}

async function refreshWebhooks() {
  const data = await api('/api/webhooks/activity');
  const webhooks = Array.isArray(data) ? data : [];
  
  document.getElementById('totalWebhooks').textContent = webhooks.length;
  document.getElementById('successTrades').textContent = webhooks.filter(w => w.parsed_data).length;
  document.getElementById('failedWebhooks').textContent = webhooks.filter(w => !w.parsed_data).length;
  
  if (webhooks.length > 0) {
    const lastWebhook = new Date(webhooks[0].timestamp);
    document.getElementById('lastWebhook').textContent = lastWebhook.toLocaleTimeString();
    
    // Update live feed (last 5 webhooks)
    const recentWebhooks = webhooks.slice(0, 5);
    document.getElementById('liveFeed').innerHTML = recentWebhooks.map(webhook => `
      <div class="feed-item">
        <strong>${webhook.strategy_name}</strong> - ${webhook.parsed_data ? webhook.parsed_data.action : 'PARSE ERROR'} 
        ${webhook.parsed_data ? webhook.parsed_data.symbol : ''} 
        <span style="float: right; color: #8b949e; font-size: 0.8em;">
          ${new Date(webhook.timestamp).toLocaleTimeString()}
        </span>
        <br><small style="color: #8b949e;">${webhook.raw_message}</small>
      </div>
    `).join('') || '<p style="color: #8b949e;">No recent activity</p>';
    
    // Update activity list (last 10 webhooks)
    document.getElementById('activityList').innerHTML = webhooks.slice(0, 10).map(webhook => `
      <div class="item">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
          <strong>${webhook.strategy_name} (ID: ${webhook.strategy_id})</strong>
          <span style="color: #8b949e; font-size: 0.8em;">${new Date(webhook.timestamp).toLocaleString()}</span>
        </div>
        <div style="background: #21262d; padding: 8px; border-radius: 4px; font-family: monospace; font-size: 0.9em;">
          ${webhook.raw_message}
        </div>
        ${webhook.parsed_data ? `
          <div style="margin-top: 5px; font-size: 0.9em;">
            <span style="color: #244c48;">Action:</span> ${webhook.parsed_data.action} | 
            <span style="color: #244c48;">Symbol:</span> ${webhook.parsed_data.symbol} | 
            <span style="color: #244c48;">Qty:</span> ${webhook.parsed_data.quantity} | 
            <span style="color: #244c48;">Price:</span> $${webhook.parsed_data.price.toFixed(4)}
          </div>
        ` : '<div style="color: #962c2f; font-size: 0.9em;">⚠️ Failed to parse message</div>'}
      </div>
    `).join('') || '<p style="color: #8b949e;">No webhook activity yet</p>';
  } else {
    document.getElementById('lastWebhook').textContent = 'Never';
    document.getElementById('liveFeed').innerHTML = '<p style="color: #8b949e;">Waiting for signals...</p>';
    document.getElementById('activityList').innerHTML = '<p style="color: #8b949e;">No activity yet</p>';
  }
}

async function testParsing() {
  const message = document.getElementById('testMessage').value.trim();
  if (!message) {
    alert('Please enter a test message');
    return;
  }
  
  const data = await api('/webhook/debug-parse', 'POST', message);
  
  const resultDiv = document.getElementById('parseResult');
  if (data.parsed_result && !data.parsed_result.error) {
    resultDiv.innerHTML = `
      <div style="background: #0d1117; border: 1px solid #244c48; padding: 12px; border-radius: 6px; margin-top: 10px;">
        <h5 style="color: #244c48; margin-bottom: 10px;">✅ Parse Success</h5>
        <p><strong>Action:</strong> ${data.parsed_result.action}</p>
        <p><strong>Symbol:</strong> ${data.parsed_result.symbol}</p>
        <p><strong>Quantity:</strong> ${data.parsed_result.quantity}</p>
      </div>
    `;
  } else {
    resultDiv.innerHTML = `
      <div style="background: #0d1117; border: 1px solid #962c2f; padding: 12px; border-radius: 6px; margin-top: 10px;">
        <h5 style="color: #962c2f; margin-bottom: 10px;">❌ Parse Failed</h5>
        <p>Unable to parse the message. Check format.</p>
      </div>
    `;
  }
}

// Copy URL helper
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