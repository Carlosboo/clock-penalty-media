import assert from 'node:assert/strict';
import test from 'node:test';
import { anchors, captionGroups, DURATION, FPS, ROWS, SAFE } from './timeline.mjs';

test('effects anchor to spoken technology words, never guessed timings', () => {
  const words = ROWS.map((row, i) => ({ word: row.trigger, start: i + 1, end: i + 1.5 }));
  assert.deepEqual(anchors(words), [30, 60, 90, 120]);
  assert.throws(() => anchors([]), /Missing effect anchor/);
});

test('captions contain at most three words, respect pauses and avoid overlaps', () => {
  const words = ['Esto', 'es', 'una', 'prueba.', 'Nueva', 'frase'].map((word, i) => ({
    word,
    start: i * 0.3,
    end: i * 0.3 + 0.2,
  }));
  const groups = captionGroups(words);
  assert.equal(groups.flatMap((g) => g.words).length, words.length);
  groups.forEach((g, i) => {
    assert.ok(g.words.length <= 3);
    assert.ok(g.start < g.end);
    if (i) assert.ok(groups[i - 1].end <= g.start);
  });
  assert.throws(() => captionGroups([{ word: 'bad', start: 1, end: 0 }]), /Invalid/);
  assert.throws(() => captionGroups([{ word: 'bad', start: 0, end: NaN }]), /Invalid/);
});

test('composition and graphic safe bounds match vertical delivery', () => {
  assert.equal(DURATION / FPS, 26.833333333333332);
  assert.ok(SAFE.top >= 130 && SAFE.bottom <= 1460);
  assert.ok(SAFE.left >= 0 && SAFE.right <= 950);
});
