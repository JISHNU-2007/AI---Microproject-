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

const rows = [
  ["TXN-84A21","Card","₹84,500","0.94","High","Blocked","Unusual velocity"],
  ["TXN-84A20","UPI","₹18,200","0.71","Review","Review","Location deviation"],
  ["TXN-84A19","Card","₹4,850","0.12","Low","Approved","Normal behavior"],
  ["TXN-84A18","Wallet","₹32,700","0.68","Review","Review","Device mismatch"],
  ["TXN-84A17","UPI","₹2,100","0.08","Low","Approved","Normal behavior"]
];

function filterRows(){
  const q=document.getElementById('search').value.toLowerCase();
  const f=document.getElementById('riskFilter').value;
  const body=document.getElementById('transactionBody');
  body.innerHTML=rows.filter(r=>(f==="all"||r[4]===f)&&r.join(" ").toLowerCase().includes(q)).map(r=>{
    const scoreClass=r[4]==="High"?"high-score":r[4]==="Review"?"review-score":"low-score";
    const badgeClass=r[4]==="High"?"high-badge":r[4]==="Review"?"review-badge":"low-badge";
    return `<tr><td><b>${r[0]}</b><small>just now</small></td><td>${r[1]}</td><td>${r[2]}</td><td><span class="score ${scoreClass}">${r[3]}</span></td><td><span class="badge ${badgeClass}">${r[5]}</span></td><td>${r[6]}</td></tr>`;
  }).join("");
}
function simulateTransaction(){
  const id="TXN-"+Math.floor(10000+Math.random()*89999);
  const risk=(Math.random()*.95+.03).toFixed(2);
  const level=risk>.78?"High":risk>.45?"Review":"Low";
  const decision=level==="High"?"Blocked":level==="Review"?"Review":"Approved";
  const signal=level==="High"?"Velocity anomaly":level==="Review"?"Behavior deviation":"Normal behavior";
  rows.unshift([id,"Card","₹"+(Math.floor(Math.random()*90000)+1000).toLocaleString("en-IN"),risk,level,decision,signal]);
  filterRows();
  document.getElementById('transactions').scrollIntoView({behavior:'smooth'});
}
function scrollToSection(id){document.getElementById(id).scrollIntoView({behavior:'smooth'})}

new Chart(document.getElementById('riskChart'),{
  type:'line',
  data:{labels:['00','03','06','09','12','15','18','21'],datasets:[
    {label:'Transactions',data:[8200,10300,9800,15100,17600,19200,21400,22500],borderWidth:2,tension:.35},
    {label:'Alerts',data:[220,270,245,310,360,335,410,390],borderWidth:2,tension:.35}
  ]},
  options:{responsive:true,plugins:{legend:{position:'bottom',labels:{boxWidth:10,font:{size:10}}}},scales:{y:{grid:{color:'#edf1f5'},ticks:{font:{size:10}}},x:{grid:{display:false},ticks:{font:{size:10}}}}}
});
new Chart(document.getElementById('donutChart'),{
  type:'doughnut',
  data:{labels:['Low risk','Review','High risk'],datasets:[{data:[91.4,7.2,1.4],borderWidth:0}]},
  options:{cutout:'72%',plugins:{legend:{display:false}}}
});
