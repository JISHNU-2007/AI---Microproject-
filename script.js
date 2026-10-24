/* ── Theme toggle & Auth ──────────────────────────────────────── */
(function(){
  const root = document.documentElement;
  const saved = localStorage.getItem('sb-theme');
  if(saved === 'dark') root.setAttribute('data-theme','dark');
  document.addEventListener('DOMContentLoaded', function(){
    // Theme toggle
    const btn = document.getElementById('themeToggle');
    if(btn){
      btn.addEventListener('click', function(){
        const isDark = root.getAttribute('data-theme') === 'dark';
        if(isDark){
          root.removeAttribute('data-theme');
          localStorage.setItem('sb-theme','light');
        } else {
          root.setAttribute('data-theme','dark');
          localStorage.setItem('sb-theme','dark');
        }
      });
    }
    // Logout
    const logoutBtn = document.getElementById('logoutBtn');
    if(logoutBtn){
      logoutBtn.addEventListener('click', function(){
        localStorage.removeItem('sb-admin-auth');
        sessionStorage.removeItem('sb-admin-auth');
        window.location.replace('login.html');
      });
    }
  });
})();

const API_BASE = window.location.origin.includes(':8000') ? window.location.origin : 'http://localhost:8000';

let rows = [
  ["TXN-84A21","Card","₹84,500","0.94","High","Blocked","Unusual velocity"],
  ["TXN-84A20","UPI","₹18,200","0.71","Review","Review","Location deviation"],
  ["TXN-84A19","Card","₹4,850","0.12","Low","Approved","Normal behavior"],
  ["TXN-84A18","Wallet","₹32,700","0.68","Review","Review","Device mismatch"],
  ["TXN-84A17","UPI","₹2,100","0.08","Low","Approved","Normal behavior"]
];

function filterRows(){
  const q=(document.getElementById('search')?.value || '').toLowerCase();
  const f=document.getElementById('riskFilter')?.value || 'all';
  const body=document.getElementById('transactionBody');
  if(!body) return;
  body.innerHTML=rows.filter(r=>(f==="all"||r[4]===f)&&r.join(" ").toLowerCase().includes(q)).map(r=>{
    const scoreClass=r[4]==="High"?"high-score":r[4]==="Review"?"review-score":"low-score";
    const badgeClass=r[4]==="High"?"high-badge":r[4]==="Review"?"review-badge":"low-badge";
    return `<tr><td><b>${r[0]}</b><small>live</small></td><td>${r[1]}</td><td>${r[2]}</td><td><span class="score ${scoreClass}">${r[3]}</span></td><td><span class="badge ${badgeClass}">${r[5]}</span></td><td>${r[6]}</td></tr>`;
  }).join("");
}

async function loadTransactions(){
  try {
    const res = await fetch(`${API_BASE}/api/transactions?limit=50`);
    if(res.ok){
      const data = await res.json();
      if(Array.isArray(data) && data.length > 0){
        rows = data.map(t => [
          t.transaction_id,
          t.channel,
          t.amount_display || `₹${Number(t.amount).toLocaleString('en-IN')}`,
          String(t.risk_score),
          t.risk_level,
          t.decision,
          t.signal
        ]);
        filterRows();
      }
    }
  } catch(e) {
    console.warn('Backend not reachable, using static transaction data.', e);
  }
}

async function simulateTransaction(){
  const amount = Math.floor(Math.random() * 90000) + 1000;
  const hour   = Math.floor(Math.random() * 24);
  const vel    = Math.floor(Math.random() * 12);
  const channels = ['Card', 'UPI', 'NetBanking', 'Wallet'];
  const channel = channels[Math.floor(Math.random() * channels.length)];

  try {
    const res = await fetch(`${API_BASE}/api/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        amount: amount,
        channel: channel,
        transaction_hour: hour,
        transactions_last_hour: vel,
        avg_amount_last_7d: 5000,
        amount_to_avg_ratio: +(amount / 5000).toFixed(2),
        is_new_merchant: Math.random() > 0.7 ? 1 : 0,
        merchant_category: 'Electronics',
        location: 'Mumbai',
        device: 'mobile',
        is_international: Math.random() > 0.85 ? 1 : 0,
        days_since_last_transaction: 1,
        weekend_flag: 0
      })
    });
    if(res.ok){
      const t = await res.json();
      rows.unshift([
        t.transaction_id,
        t.channel,
        t.amount_display,
        String(t.risk_score),
        t.risk_level,
        t.decision,
        t.signal
      ]);
      filterRows();
      document.getElementById('transactions').scrollIntoView({ behavior: 'smooth' });
      return;
    }
  } catch(e) {
    console.warn('Predict API call failed, falling back to local simulation', e);
  }

  // Fallback simulation
  const id="TXN-"+Math.floor(10000+Math.random()*89999);
  const risk=(Math.random()*.95+.03).toFixed(2);
  const level=risk>.78?"High":risk>.45?"Review":"Low";
  const decision=level==="High"?"Blocked":level==="Review"?"Review":"Approved";
  const signal=level==="High"?"Velocity anomaly":level==="Review"?"Behavior deviation":"Normal behavior";
  rows.unshift([id,"Card","₹"+amount.toLocaleString("en-IN"),risk,level,decision,signal]);
  filterRows();
  document.getElementById('transactions').scrollIntoView({behavior:'smooth'});
}

function scrollToSection(id){document.getElementById(id).scrollIntoView({behavior:'smooth'})}

let riskChartInstance = null;
let donutChartInstance = null;

function initCharts(){
  const riskEl = document.getElementById('riskChart');
  if(riskEl){
    riskChartInstance = new Chart(riskEl,{
      type:'line',
      data:{labels:['00','03','06','09','12','15','18','21'],datasets:[
        {label:'Transactions',data:[8200,10300,9800,15100,17600,19200,21400,22500],borderWidth:2,tension:.35},
        {label:'Alerts',data:[220,270,245,310,360,335,410,390],borderWidth:2,tension:.35}
      ]},
      options:{responsive:true,plugins:{legend:{position:'bottom',labels:{boxWidth:10,font:{size:10}}}},scales:{y:{grid:{color:'#edf1f5'},ticks:{font:{size:10}}},x:{grid:{display:false},ticks:{font:{size:10}}}}}
    });
  }

  const donutEl = document.getElementById('donutChart');
  if(donutEl){
    donutChartInstance = new Chart(donutEl,{
      type:'doughnut',
      data:{labels:['Low risk','Review','High risk'],datasets:[{data:[91.4,7.2,1.4],borderWidth:0}]},
      options:{cutout:'72%',plugins:{legend:{display:false}}}
    });
  }
}

async function loadCharts(){
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    if(res.ok){
      const s = await res.json();
      const statsEls = document.querySelectorAll('.stats .stat strong');
      if(statsEls.length >= 4){
        statsEls[0].textContent = Number(s.total_transactions).toLocaleString('en-IN');
        statsEls[1].textContent = Number(s.high_risk_alerts).toLocaleString('en-IN');
        statsEls[2].textContent = (s.detection_precision * 100).toFixed(1) + '%';
        statsEls[3].textContent = s.avg_scoring_ms + ' ms';
      }
      if(s.risk_distribution && donutChartInstance){
        donutChartInstance.data.datasets[0].data = [
          s.risk_distribution.low || 91.4,
          s.risk_distribution.review || 7.2,
          s.risk_distribution.high || 1.4
        ];
        donutChartInstance.update();
      }
    }
  } catch(e){
    console.warn('Could not load dynamic stats', e);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  filterRows();
  initCharts();
  loadTransactions();
  loadCharts();
});
