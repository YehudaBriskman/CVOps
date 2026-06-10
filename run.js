async function runExtraction() {
  const res = await fetch('http://localhost:8000/extract', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session: name, mode, interval: val })
  });
  const data = await res.json();
  log('ok', `✓ ${data.frames_saved} frames extracted`);
}