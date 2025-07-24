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

const formatLTV = (ltv) => {
  const ltvValue = parseFloat(ltv) || 0;
  let colorClass = '#244c48'; // healthy green
  if (ltvValue > 80) colorClass = '#962c2f'; // critical red
  else if (ltvValue > 70) colorClass = '#f39c12'; // warning orange
  else if (ltvValue > 60) colorClass = '#9c4d30'; // caution amber
  
  return `<span style="color: ${colorClass}; font-weight: bold;">${ltvValue.toFixed(1)}%</span>`;
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

async function refreshLoanPositions() {
  if (!activeClientId) return;
  const loans = await api(`/api/loans/${activeClientId}`);
  if (loans.error) return console.warn(loans.error);
  
  if (loans.success && loans.loan_summary) {
    const summary = loans.loan_summary;
    const positions = loans.loan_positions || [];
    
    // Update loan summary display
    const loanSummaryHtml = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-bottom: 15px;">
        <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
          <div style="font-size: 1.3em; font-weight: bold; color: #58a6ff;">${summary.active_loans}</div>
          <div style="font-size: 0.8em; color: #8b949e;">Active Loans</div>
        </div>
        <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
          <div style="font-size: 1.3em; font-weight: bold; color: #9c4d30;">${summary.total_collateral_btc.toFixed(4)}</div>
          <div style="font-size: 0.8em; color: #8b949e;">Collateral (BTC)</div>
        </div>
        <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
          <div style="font-size: 1.3em; font-weight: bold; color: #962c2f;">${summary.total_debt_btc.toFixed(4)}</div>
          <div style="font-size: 0.8em; color: #8b949e;">Debt (BTC)</div>
        </div>
        <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
          <div style="font-size: 1.3em; font-weight: bold;">${formatLTV(summary.overall_ltv)}</div>
          <div style="font-size: 0.8em; color: #8b949e;">Overall LTV</div>
        </div>
      </div>
    `;
    
    // Display individual loan positions
    if (positions.length > 0) {
      const positionsHtml = positions.map(loan => `
        <div style="background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 12px; margin: 8px 0;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <strong style="color: #f0f6fc;">${loan.loan_coin} loan (${loan.collateral_coin} collateral)</strong>
            <span style="font-size: 0.8em; color: ${loan.current_ltv > 80 ? '#962c2f' : loan.current_ltv > 70 ? '#f39c12' : '#244c48'};">
              ${loan.status.toUpperCase()}
            </span>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; font-size: 0.9em;">
            <span>Principal: <strong>${loan.principal_amount.toFixed(4)} ${loan.loan_coin}</strong></span>
            <span>Collateral: <strong>${loan.collateral_amount.toFixed(4)} ${loan.collateral_coin}</strong></span>
            <span>LTV: ${formatLTV(loan.current_ltv)}</span>
            <span>Liquidation LTV: <strong>${loan.liquidation_ltv.toFixed(1)}%</strong></span>
            <span>Interest Rate: <strong>${(loan.interest_rate * 100).toFixed(2)}%</strong></span>
            <span>Order ID: <small>${loan.order_id}</small></span>
          </div>
        </div>
      `).join('');
      
      document.getElementById('loanPositions').innerHTML = loanSummaryHtml + positionsHtml;
    } else {
      document.getElementById('loanPositions').innerHTML = loanSummaryHtml + '<p style="color: #8b949e;">No active loans found</p>';
    }
  } else {
    document.getElementById('loanPositions').innerHTML = '<p style="color: #8b949e;">No loan data available</p>';
  }
}

async function refreshLTVStatus() {
  if (!activeClientId) return;
  const data = await api(`/api/ltv-status/${activeClientId}`);
  if (data.error) {
    document.getElementById('ltvStatus').innerHTML = `<p style="color: #962c2f;">Error: ${data.error}</p>`;
    return;
  }
  
  const ltv = data.ltv_status;
  const healthClass = getHealthClass(ltv.health_status);
  
  document.getElementById('ltvStatus').innerHTML = `
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 15px;">
      <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
        <div style="font-size: 1.5em; font-weight: bold;">${formatLTV(ltv.current_ltv)}</div>
        <div style="font-size: 0.8em; color: #8b949e;">Current LTV</div>
      </div>
      <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
        <div style="font-size: 1.5em; font-weight: bold; color: #58a6ff;">${ltv.target_ltv}%</div>
        <div style="font-size: 0.8em; color: #8b949e;">Target LTV</div>
      </div>
      <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
        <div style="font-size: 1.5em; font-weight: bold; color: ${healthClass === 'positive' ? '#244c48' : healthClass === 'warning' ? '#9c4d30' : '#962c2f'};">
          ${ltv.health_status.toUpperCase()}
        </div>
        <div style="font-size: 0.8em; color: #8b949e;">Health Status</div>
      </div>
      <div style="text-align: center; padding: 10px; background: #0d1117; border-radius: 6px;">
        <div style="font-size: 1.5em; font-weight: bold; color: ${ltv.needs_rebalance ? '#9c4d30' : '#244c48'};">
          ${ltv.needs_rebalance ? 'NEEDED' : 'OK'}
        </div>
        <div style="font-size: 0.8em; color: #8b949e;">Rebalance</div>
      </div>
    </div>
    <div style="background: #0d1117; padding: 15px; border-radius: 6px; margin-top: 15px;">
      <h5 style="color: #58a6ff; margin-bottom: 10px;">📋 Recommendations:</h5>
      ${ltv.recommended_actions.map(action => `<p style="font-size: 0.9em; margin: 5px 0; color: #f0f6fc;">• ${action}</p>`).join('')}
    </div>
  `;
}

function getHealthClass(health) {
  switch(health.toLowerCase()) {
    case 'healthy': return 'positive';
    case 'caution': return 'warning';
    case 'warning': return 'warning';
    case 'critical': return 'negative';
    default: return '';
  }
}

function refreshAll() {
  refreshBalance();
  refreshPositions();
  refreshEarn();
  refreshLoanPositions();
  refreshLTVStatus();
}