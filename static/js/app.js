/**
 * app.js — Minimal vanilla JS for the game UI.
 *
 * Responsibilities:
 *   1. Floating damage number animations triggered by HTMX boss HP changes
 *   2. Color picker interaction on hero forms
 *   3. Time formatting for event feed
 *   4. HTMX event hooks (flash hero card on update, etc.)
 */

'use strict';

// ── Damage Number Animation ────────────────────────────────────────────────────

/**
 * Spawn a floating number at (x, y) relative to the viewport.
 * @param {number} value - Damage/heal amount to show
 * @param {'hit'|'crit'|'heal'} type - Controls color/size
 * @param {number} x - Page X coordinate
 * @param {number} y - Page Y coordinate
 */
function spawnDamageNumber(value, type = 'hit', x, y) {
  const el = document.createElement('div');
  el.className = `damage-number ${type}`;
  el.textContent = type === 'crit' ? `${value} CRIT!` : (type === 'heal' ? `+${value}` : `-${value}`);

  // Position relative to viewport with slight random spread
  const spread = (Math.random() - 0.5) * 80;
  el.style.left = `${x + spread}px`;
  el.style.top  = `${y}px`;
  el.style.position = 'fixed';

  document.body.appendChild(el);
  el.addEventListener('animationend', () => el.remove());
}

// Attach to boss figure clicks (demo/debug — can remove in prod)
document.addEventListener('DOMContentLoaded', () => {
  const bossFigure = document.querySelector('.boss-figure');
  if (bossFigure) {
    bossFigure.addEventListener('click', (e) => {
      spawnDamageNumber(Math.floor(Math.random() * 50 + 10), 'hit', e.clientX, e.clientY);
    });
  }
});


// ── HTMX Hooks ────────────────────────────────────────────────────────────────

// After the boss partial refreshes, check if HP dropped — show damage number
let lastBossHp = null;

document.addEventListener('htmx:afterSettle', (evt) => {
  const bossBar = document.querySelector('.boss-hp-bar-fill');
  if (!bossBar) return;

  const currentHp = parseInt(bossBar.dataset.hp || '0', 10);
  if (lastBossHp !== null && currentHp < lastBossHp) {
    const damage = lastBossHp - currentHp;
    const bossScene = document.querySelector('.boss-scene');
    if (bossScene) {
      const rect = bossScene.getBoundingClientRect();
      spawnDamageNumber(damage, damage > 150 ? 'crit' : 'hit',
        rect.left + rect.width / 2,
        rect.top + rect.height * 0.35
      );
    }
  }
  lastBossHp = currentHp;
});

// Flash hero card when it updates
document.addEventListener('htmx:afterSettle', (evt) => {
  const target = evt.detail.elt;
  if (target && target.classList && target.classList.contains('hero-column')) {
    target.querySelectorAll('.hero-card').forEach(card => {
      card.classList.add('animate-fade-in');
      setTimeout(() => card.classList.remove('animate-fade-in'), 400);
    });
  }
});


// ── Color Picker ───────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.color-picker').forEach(picker => {
    const input = picker.closest('form').querySelector('input[name="color"]');
    picker.querySelectorAll('.color-swatch').forEach(swatch => {
      swatch.addEventListener('click', () => {
        picker.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('selected'));
        swatch.classList.add('selected');
        if (input) input.value = swatch.dataset.color;
      });
    });
    // Pre-select current value
    if (input && input.value) {
      const current = picker.querySelector(`.color-swatch[data-color="${input.value}"]`);
      if (current) current.classList.add('selected');
    }
  });
});


// ── Relative Timestamps ────────────────────────────────────────────────────────

function timeAgo(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString.replace(' ', 'T'));
  const diff = Math.floor((Date.now() - date) / 1000);
  if (diff < 60)  return `${diff}s ago`;
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-timestamp]').forEach(el => {
    el.textContent = timeAgo(el.dataset.timestamp);
  });
});

// Re-run after HTMX swaps
document.addEventListener('htmx:afterSettle', () => {
  document.querySelectorAll('[data-timestamp]').forEach(el => {
    el.textContent = timeAgo(el.dataset.timestamp);
  });
});


// ── Task completion confirmation ───────────────────────────────────────────────

document.addEventListener('submit', (evt) => {
  const form = evt.target;
  if (form.dataset.confirm) {
    if (!confirm(form.dataset.confirm)) {
      evt.preventDefault();
    }
  }
});


// ── Auto-dismiss flash messages ────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.alert').forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.5s';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 500);
    }, 4000);
  });
});
