export const FPS = 30;
export const DURATION = 805;
export const SAFE = { left: 90, right: 940, top: 150, bottom: 1450 };
export const ROWS = [
  { title: 'Supabase', detail: 'Base de datos', kind: 'database', trigger: 'Supabase' },
  { title: 'Cloudflare Pages', detail: 'Frontend web', kind: 'cloud', trigger: 'Cloudflare' },
  { title: 'WebSockets', detail: 'Comunicación en partida', kind: 'live', trigger: 'WebSockets' },
  { title: 'Turnstile', detail: 'Filtro antibots', kind: 'shield', trigger: 'Turnstile' },
];

export function anchors(words) {
  return ROWS.map((row) => {
    const word = words.find((item) => item.word === row.trigger);
    if (!word) throw new Error(`Missing effect anchor: ${row.trigger}`);
    return Math.round(word.start * FPS);
  });
}

export function captionGroups(words) {
  const groups = [];
  let group = [];
  for (const word of words) {
    if (
      !Number.isFinite(word.start) ||
      !Number.isFinite(word.end) ||
      word.start < 0 ||
      word.end <= word.start
    ) {
      throw new Error('Invalid subtitle word timing');
    }
    const width = [...group, word].reduce((sum, item) => sum + item.word.length, 0);
    if (
      group.length &&
      (group.length === 3 || width > 21 || word.start - group.at(-1).end > 0.35)
    ) {
      groups.push(group);
      group = [];
    }
    group.push(word);
    if (/[.,!?]$/.test(word.word)) {
      groups.push(group);
      group = [];
    }
  }
  if (group.length) groups.push(group);
  return groups.map((items, i) => ({
    words: items,
    start: items[0].start,
    end: Math.min(items.at(-1).end + 0.1, groups[i + 1]?.[0].start ?? Infinity),
  }));
}
