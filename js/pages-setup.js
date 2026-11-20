"use strict";
const form = document.getElementById('link-form');
const output = document.getElementById('generated-links');
form.addEventListener('submit', (event) => {
  event.preventDefault();
  const input = document.getElementById('backend-url').value.trim().replace(/\/+$/, '');
  let backend;
  try { backend = new URL(input); }
  catch { output.textContent = 'Enter the full HTTPS Render URL.'; return; }
  if (backend.protocol !== 'https:' || backend.pathname !== '/' || backend.search || backend.hash) {
    output.textContent = 'Use only the HTTPS service origin, for example https://example.onrender.com'; return;
  }
  output.replaceChildren();
  const title = document.createElement('h3'); title.textContent = 'Ready-to-paste links'; output.append(title);
  const endpoints = [
    ['Synchronized Top 3 and donation alert', 'pages-overlay.html', 'top3-alert'],
    ['Top 3 leaderboard', 'pages-overlay.html', 'top3'],
    ['Donation alert', 'pages-overlay.html', 'alert'],
    ['Full standings', 'pages-overlay.html', 'full'],
    ['Goals progress bar (toggle in operator)', 'pages-overlay.html', 'goals'],
    ['Producer scoreboard', 'pages-producer.html', null],
  ];
  for (const [name, page, graphic] of endpoints) {
    const url = new URL(page, location.href);
    url.searchParams.set('backend', backend.origin);
    if (graphic) url.searchParams.set('graphic', graphic);
    if (graphic === 'top3' && document.getElementById('donation-only-top3').checked) {
      url.searchParams.set('show', 'on-donation');
    }
    const row = document.createElement('div'); row.className = 'panel';
    const label = document.createElement('strong'); label.textContent = name;
    const link = document.createElement('a'); link.textContent = url.href; link.href = url.href;
    link.target = '_blank'; link.rel = 'noopener noreferrer';
    const copy = document.createElement('button'); copy.type='button'; copy.className='btn ghost small'; copy.textContent='Copy URL';
    copy.addEventListener('click', async () => { try { await navigator.clipboard.writeText(url.href); copy.textContent='Copied'; } catch { copy.textContent='Select and copy the URL above'; }});
    row.append(label, link, copy); output.append(row);
  }
});
