// Shared WebSocket connection to /ws/dashboard. Pages listen via:
//   window.addEventListener('novatech:worker_update', e => { e.detail ... })
//   window.addEventListener('novatech:alert', e => { e.detail ... })
(function () {
  const dot = document.getElementById('wsDot');
  const pill = document.getElementById('wsStatusPill');

  function setStatus(connected) {
    if (!dot || !pill) return;
    dot.className = 'dot ' + (connected ? 'green' : 'red');
    pill.lastChild.textContent = connected ? ' live' : ' disconnected';
  }

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws/dashboard`);

    ws.onopen = () => setStatus(true);
    ws.onclose = () => { setStatus(false); setTimeout(connect, 2000); };
    ws.onerror = () => ws.close();

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        window.dispatchEvent(new CustomEvent('novatech:' + msg.type, { detail: msg }));
      } catch (e) { /* ignore malformed */ }
    };

    // keep-alive ping every 20s so proxies don't kill idle connections
    setInterval(() => { if (ws.readyState === 1) ws.send('ping'); }, 20000);
  }
  connect();
})();
