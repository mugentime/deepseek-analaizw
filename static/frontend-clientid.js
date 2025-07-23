// ------------------------------------------------------------
// Global state for active client ID
// ------------------------------------------------------------
let activeClientId = null;

//-------------------------------------------------------------
// Generic helper to call the backend
//-------------------------------------------------------------
async function api(url, method = 'GET', body = null) {
  try {
    const options = {
      method,
      headers: {'Content-Type': 'application/json'}
    };
    
    if (body) {
      options.body = JSON.stringify(body);
    }
    
    const res = await fetch(url, options);
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
    status('Connected to Binance API');
  } else {
    document.getElementById('status').innerHTML = '<strong style="color: #962c2f;">❌ Connection Failed</strong>';
    status('Connection failed: ' + (data.error || 'Unknown error'));
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
  return `<span style="color: #58a6ff; font-weight: bold;">${amtValue.toFixed(6)}</span>`;
};

const formatDailyRewards = (rewards) => {
  const rewardValue = parseFloat(rewards) || 0;
  return `<span style="color: #9c4d30; font-weight: bold;">$${rewardValue.toFixed(4)}</span>`;
};

const formatTimestamp = (timestamp) => {
  try {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  } catch {
    return 'Unknown';
  }
};

//-------------------------------------------------------------
// UI refresh helpers use activeClientId
//-------------------------------------------------------------
async function refreshBalance() {
  if (!activeClientId) return;
  const bal = await api(`/api/balance/${activeClientId}`);
  if (bal.error) {
    console.warn(bal.error);
    document.getElementById('wallet-balance').innerHTML = `<p style="color: #962c2f;">Error: ${bal.error}</p>`;
    return;
  }
  
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
  if (pos.error) {
    console.warn(pos.error);
    document.getElementById('positions-list').innerHTML = `<p style="color: #962c2f;">Error: ${pos.error}</p>`;
    return;
  }
  
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
  if (earn.error) {
    console.warn(earn.error);
    document.getElementById('earn-summary').innerHTML = `<p style="color: #962c2f;">Error: ${earn.error}</p>`;
    document.getElementById('earn-positions').innerHTML = '';
    return;
  }
  
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
  if (data.error) {
    document.getElementById('trackedPositions').innerHTML = `<p style="color: #962c2f;">Error: ${data.error}</p>`;
    return;
  }
  
  if (!data.tracked_positions || data.tracked_positions.length === 0) {
    document.getElementById('trackedPositions').innerHTML = '<p style="color: #8b949e;">No tracked positions</p>';
    return;
  }
  
  document.getElementById('trackedPositions').innerHTML = data.tracked_positions.map(pos => `
    <div style="background: #0d1117; padding: 10px; margin: 5px 0; border-radius: 4px; border: 1px solid #30363d;">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <strong style="color: #f0f6fc;">${pos.symbol} ${pos.side}</strong>
        <span style="color: #8b949e; font-size: 0.8em;">${pos.age_minutes}m ago</span>
      </div>
      <div style="font-size: 0.9em; color: #8b949e; margin-top: 3px;">
        Qty: ${pos.quantity} | Entry: $${pos.entry_price.toFixed(4)} | Strategy: ${pos.strategy_name || pos.strategy_id}
      </div>
    </div>
  `).join('');
}

async function loadStrategies() {
  const data = await api('/api/strategies');
  if (data.error) {
    document.getElementById('strategiesList').innerHTML = `<p style="color: #962c2f;">Error: ${data.error}</p>`;
    return;
  }
  
  const strategies = data.strategies || [];
  
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
      ${strategy.description ? `<p style="color: #8b949e; font-size: 0.9em; margin-bottom: 8px;">${strategy.description}</p>` : ''}
      <div style="display: flex; gap: 8px; align-items: center;">
        <button onclick="copyURL(${strategy.id})" style="background: #244c48; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; cursor: pointer;">📋 Copy URL</button>
        <span style="color: #8b949e; font-size: 0.8em;">ID: ${strategy.id}</span>
      </div>
    </div>
  `).join('');
  
  // Update strategies count
  document.getElementById('strategies').textContent = strategies.length;
}

async function refreshWebhooks() {
  const data = await api('/api/webhooks/activity');
  if (data.error) {
    document.getElementById('activityList').innerHTML = `<p style="color: #962c2f;">Error: ${data.error}</p>`;
    return;
  }
  
  const activities = data.activity || [];
  
  // Update stats
  document.getElementById('totalWebhooks').textContent = data.total_count || 0;
  const successCount = activities.filter(a => a.success).length;
  const failedCount = activities.filter(a => !a.success).length;
  document.getElementById('successTrades').textContent = successCount;
  document.getElementById('failedWebhooks').textContent = failedCount;
  
  const lastActivity = activities[0];
  document.getElementById('lastWebhook').textContent = lastActivity ? formatTimestamp(lastActivity.timestamp) : 'Never';
  
  // Update activity list
  if (activities.length === 0) {
    document.getElementById('activityList').innerHTML = '<p style="color: #8b949e;">No webhook activity yet</p>';
    document.getElementById('liveFeed').innerHTML = 'Waiting for signals...';
    return;
  }
  
  // Live feed (last 5 activities)
  const recentActivities = activities.slice(0, 5);
  document.getElementById('liveFeed').innerHTML = recentActivities.map(activity => `
    <div class="feed-item" style="border-left-color: ${activity.success ? '#244c48' : '#962c2f'};">
      <div style="font-size: 0.8em; color: #8b949e;">${formatTimestamp(activity.timestamp)} - ${activity.strategy_name || `Strategy ${activity.strategy_id}`}</div>
      <div style="color: ${activity.success ? '#244c48' : '#962c2f'}; font-weight: bold;">
        ${activity.success ? '✅' : '❌'} ${activity.raw_message || activity.error}
      </div>
    </div>
  `).join('');
  
  // Full activity list
  document.getElementById('activityList').innerHTML = activities.map(activity => `
    <div style="background: #0d1117; padding: 10px; margin: 5px 0; border-radius: 4px; border: 1px solid #30363d; border-left: 3px solid ${activity.success ? '#244c48' : '#962c2f'};">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
        <span style="color: ${activity.success ? '#244c48' : '#962c2f'}; font-weight: bold;">
          ${activity.success ? '✅' : '❌'} ${activity.strategy_name || `Strategy ${activity.strategy_id}`}
        </span>
        <span style="color: #8b949e; font-size: 0.8em;">${formatTimestamp(activity.timestamp)}</span>
      </div>
      <div style="font-family: monospace; font-size: 0.9em; color: #f0f6fc; margin-bottom: 5px;">
        ${activity.raw_message || 'No message'}
      </div>
      ${activity.success && activity.parsed_data ? `
        <div style="font-size: 0.8em; color: #8b949e;">
          Action: ${activity.parsed_data.action} | Symbol: ${activity.parsed_data.symbol} | 
          ${activity.parsed_data.quantity ? `Qty: ${activity.parsed_data.quantity} | ` : ''}
          Price: $${activity.parsed_data.price ? activity.parsed_data.price.toFixed(4) : '0.0000'}
        </div>
      ` : ''}
      ${!activity.success && activity.error ? `
        <div style="color: #962c2f; font-size: 0.8em;">Error: ${activity.error}</div>
      ` : ''}
    </div>
  `).join('');
}

// Strategy management
async function createStrategy() {
  const name = document.getElementById('strategyName').value.trim();
  const description = document.getElementById('strategyDesc').value.trim();
  
  if (!name) {
    status('Please enter a strategy name');
    return;
  }
  
  const data = await api('/api/strategies', 'POST', {
    name: name,
    description: description
  });
  
  if (data.success) {
    document.getElementById('strategyName').value = '';
    document.getElementById('strategyDesc').value = '';
    status(`Strategy "${name}" created with ID ${data.strategy_id}`);
    loadStrategies();
  } else {
    status('Failed to create strategy: ' + (data.error || 'Unknown error'));
  }
}

// Test message parsing
async function testParsing() {
  const message = document.getElementById('testMessage').value.trim();
  if (!message) {
    status('Please enter a message to test');
    return;
  }
  
  const data = await api('/webhook/debug-parse', 'POST', message);
  
  document.getElementById('parseResult').innerHTML = `
    <div style="background: #0d1117; padding: 10px; border-radius: 6px; margin-top: 10px; font-family: monospace; font-size: 0.9em;">
      <div style="color: #8b949e; margin-bottom: 5px;">Raw: "${data.raw_message}"</div>
      <div style="color: ${data.success ? '#244c48' : '#962c2f'};">
        Result: ${JSON.stringify(data.parsed_result, null, 2)}
      </div>
    </div>
  `;
}

// Check API configuration
async function checkConfig() {
  const data = await api('/api/debug/config');
  const configDiv = document.getElementById('configDebug');
  
  configDiv.style.display = configDiv.style.display === 'none' ? 'block' : 'none';
  
  if (configDiv.style.display === 'block') {
    configDiv.innerHTML = `
      <h5 style="color: #244c48; margin-bottom: 10px;">🔧 API Configuration</h5>
      <div style="display: grid; grid-template-columns: 200px 1fr; gap: 5px; font-size: 0.8em;">
        <span>API Key Set:</span><span style="color: ${data.binance_api_key_set ? '#244c48' : '#962c2f'};">${data.binance_api_key_set ? '✅ Yes' : '❌ No'}</span>
        <span>Secret Key Set:</span><span style="color: ${data.binance_secret_key_set ? '#244c48' : '#962c2f'};">${data.binance_secret_key_set ? '✅ Yes' : '❌ No'}</span>
        <span>API Key Length:</span><span>${data.api_key_length} chars</span>
        <span>Secret Key Length:</span><span>${data.secret_key_length} chars</span>
        <span>API Key Preview:</span><span style="font-family: monospace;">${data.api_key_preview}</span>
        <span>Secret Key Preview:</span><span style="font-family: monospace;">${data.secret_key_preview}</span>
        <span>Env Vars Available:</span><span>${JSON.stringify(data.env_vars_available)}</span>
      </div>
    `;
  }
}

// Copy webhook URL
function copyURL(id) {
  const url = `${location.origin}/webhook/tradingview/strategy/${id}`;
  navigator.clipboard.writeText(url).then(() => {
    status(`Webhook URL copied for strategy ${id}!`);
  }).catch(() => {
    status('Failed to copy URL - please copy manually');
  });
}

// Status message helper
function status(message) {
  const statusBar = document.getElementById('statusBar');
  statusBar.textContent = message;
  statusBar.style.background = '#244c48';
  
  setTimeout(() => {
    statusBar.textContent = 'Efficient Trading Platform - Ready';
    statusBar.style.background = '#142924';
  }, 5000);
}

// Refresh all data
function refreshAll() {
  if (activeClientId) {
    refreshBalance();
    refreshPositions();
    refreshEarn();
    refreshTracked();
  }
  loadStrategies();
  refreshWebhooks();
}