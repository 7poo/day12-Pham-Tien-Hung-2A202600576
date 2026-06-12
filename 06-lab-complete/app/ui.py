"""Single-page chat interface for the production agent."""

UI_HTML = r"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Production AI Agent</title>
  <style>
    :root{--bg:#08111f;--panel:#101c2e;--line:#24344b;--text:#eef5ff;--muted:#8fa4bf;--brand:#63e6be;--accent:#70a1ff;--danger:#ff7b7b}
    *{box-sizing:border-box}body{margin:0;color:var(--text);font:15px/1.5 Inter,system-ui,sans-serif;background:radial-gradient(circle at 10% 0,#173457 0,transparent 32%),var(--bg);min-height:100vh}
    .app{display:grid;grid-template-columns:300px 1fr;min-height:100vh}.side{padding:28px;border-right:1px solid var(--line);background:#091421cc;backdrop-filter:blur(16px)}
    .logo{display:flex;gap:12px;align-items:center;margin-bottom:36px}.mark{display:grid;place-items:center;width:42px;height:42px;border-radius:13px;background:linear-gradient(135deg,var(--brand),var(--accent));color:#07101d;font-size:22px;font-weight:900}
    h1{font-size:17px;margin:0}.sub,.hint{color:var(--muted);font-size:12px}.field{margin:18px 0}.field label{display:block;color:#b9c9dc;font-size:12px;font-weight:700;margin-bottom:7px;text-transform:uppercase;letter-spacing:.08em}
    input,textarea,button{font:inherit}input,textarea{width:100%;color:var(--text);background:#0b1727;border:1px solid var(--line);border-radius:10px;padding:11px 12px;outline:none}input:focus,textarea:focus{border-color:var(--accent)}
    button{border:0;cursor:pointer}.status{display:flex;gap:8px;align-items:center;margin-top:28px;padding:12px;border:1px solid var(--line);border-radius:12px;color:var(--muted)}.dot{width:9px;height:9px;border-radius:50%;background:#f5b942}.dot.ok{background:var(--brand);box-shadow:0 0 12px var(--brand)}
    .main{display:flex;flex-direction:column;height:100vh;max-width:1050px;width:100%;margin:auto}.top{padding:25px 32px 18px;border-bottom:1px solid var(--line)}.top h2{font-size:22px;margin:0 0 3px}.messages{flex:1;overflow:auto;padding:28px 32px}
    .empty{height:100%;display:grid;place-items:center;text-align:center;color:var(--muted)}.empty strong{display:block;color:var(--text);font-size:28px;margin-bottom:8px}.msg{display:flex;margin:0 0 20px}.msg.user{justify-content:flex-end}.bubble{max-width:min(720px,85%);padding:13px 16px;border-radius:16px;background:var(--panel);border:1px solid var(--line);white-space:pre-wrap}.user .bubble{background:linear-gradient(135deg,#23578e,#315cbf);border:0}.meta{display:block;color:#a9bdd3;font-size:11px;margin-top:7px}
    .composer{padding:16px 32px 26px}.composebox{display:flex;gap:10px;align-items:flex-end;padding:10px;border:1px solid var(--line);background:var(--panel);border-radius:16px;box-shadow:0 16px 50px #0006}.composebox textarea{border:0;background:transparent;resize:none;max-height:140px;padding:8px}.send{width:46px;height:46px;border-radius:12px;background:linear-gradient(135deg,var(--brand),var(--accent));font-size:20px;color:#07101d;font-weight:bold}.send:disabled{opacity:.4}.error{color:var(--danger)}
    @media(max-width:760px){.app{display:block}.side{padding:14px 18px;border:0;border-bottom:1px solid var(--line)}.logo{margin:0 0 12px}.side .field{display:inline-block;width:49%;margin:5px 0}.status{margin:10px 0 0}.main{height:calc(100vh - 230px)}.top,.messages,.composer{padding-left:16px;padding-right:16px}}
  </style>
</head>
<body>
<div class="app">
  <aside class="side">
    <div class="logo"><div class="mark">A</div><div><h1>Production AI Agent</h1><div class="sub">Day 12 deployment</div></div></div>
    <div class="field"><label for="key">API key</label><input id="key" type="password" placeholder="Nhập AGENT_API_KEY"></div>
    <div class="field"><label for="uid">User ID</label><input id="uid" value="demo-user" maxlength="100"></div>
    <div class="hint">API key chỉ được lưu trong tab trình duyệt này.</div>
    <div class="status"><span class="dot" id="dot"></span><span id="status">Đang kiểm tra hệ thống...</span></div>
  </aside>
  <main class="main">
    <header class="top"><h2>Trợ lý AI</h2><div class="sub">Redis conversation memory · Rate limit · Cost guard</div></header>
    <section class="messages" id="messages"><div class="empty" id="empty"><div><strong>Sẵn sàng trò chuyện</strong>Nhập API key, sau đó gửi câu hỏi đầu tiên.</div></div></section>
    <footer class="composer"><div class="composebox"><textarea id="question" rows="1" maxlength="2000" placeholder="Nhập câu hỏi..."></textarea><button class="send" id="send" title="Gửi">↑</button></div></footer>
  </main>
</div>
<script>
const key=document.querySelector('#key'),uid=document.querySelector('#uid'),q=document.querySelector('#question'),send=document.querySelector('#send'),messages=document.querySelector('#messages');
key.value=sessionStorage.getItem('agent-key')||''; uid.value=sessionStorage.getItem('agent-user')||'demo-user';
key.oninput=()=>sessionStorage.setItem('agent-key',key.value); uid.oninput=()=>sessionStorage.setItem('agent-user',uid.value);
function add(text,role,meta=''){document.querySelector('#empty')?.remove();const row=document.createElement('div');row.className='msg '+role;const bubble=document.createElement('div');bubble.className='bubble';bubble.textContent=text;if(meta){const m=document.createElement('span');m.className='meta';m.textContent=meta;bubble.appendChild(m)}row.appendChild(bubble);messages.appendChild(row);messages.scrollTop=messages.scrollHeight}
async function health(){try{const r=await fetch('/ready'),d=await r.json();document.querySelector('#dot').classList.toggle('ok',r.ok&&d.redis_connected);document.querySelector('#status').textContent=r.ok&&d.redis_connected?'Hệ thống và Redis đang hoạt động':'Hệ thống chưa sẵn sàng'}catch(e){document.querySelector('#status').textContent='Không thể kết nối hệ thống'}}
async function ask(){const question=q.value.trim(),user=uid.value.trim(),apiKey=key.value.trim();if(!apiKey){add('Vui lòng nhập API key ở thanh bên.','assistant','Thiếu API key');key.focus();return}if(!question||!user)return;q.value='';send.disabled=true;add(question,'user');try{const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':apiKey},body:JSON.stringify({user_id:user,question})});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Yêu cầu thất bại');add(d.answer,'assistant',`${d.model} · lượt ${d.conversation_turn}`)}catch(e){add(e.message,'assistant','Lỗi')}finally{send.disabled=false;q.focus()}}
send.onclick=ask;q.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask()}});health();
</script>
</body>
</html>"""
