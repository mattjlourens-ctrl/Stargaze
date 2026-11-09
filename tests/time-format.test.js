// Run: node --test tests/time-format.test.js  (results must not depend on the TZ environment variable)
const test = require('node:test');
const assert = require('node:assert/strict');
const { parseLocalWallClock, formatViewingTime, formatHourTime } = require('../frontend/time-format.js');

// ICU may separate "PM" with a narrow no-break space; normalize for comparison.
const norm = s => s.replace(/\s/g, ' ');

test('Austin time shows Central wall clock and label regardless of visitor timezone', () => {
  const hour = { time: '2026-11-09T21:00', tz_abbreviation: 'CST' };
  assert.equal(norm(formatViewingTime(hour, 'en-US')), 'Mon, Nov 9, 9:00 PM CST');
});

test('Tokyo time shows the Tokyo calendar date, not the visitor date', () => {
  const hour = { time: '2026-11-10T01:00', tz_abbreviation: 'JST' };
  assert.equal(norm(formatViewingTime(hour, 'en-US')), 'Tue, Nov 10, 1:00 AM JST');
});

test('London GMT and BST labels come from the forecast hour', () => {
  assert.equal(norm(formatViewingTime({ time: '2026-01-15T22:00', tz_abbreviation: 'GMT' }, 'en-GB')),
    'Thu 15 Jan, 22:00 GMT');
  assert.equal(norm(formatViewingTime({ time: '2026-07-15T23:00', tz_abbreviation: 'BST' }, 'en-GB')),
    'Wed 15 Jul, 23:00 BST');
});

test("a time inside the visitor's DST gap is not shifted", () => {
  // 02:30 on 2026-03-08 does not exist in US Central time; new Date() would show 3:30 AM there.
  assert.equal(norm(formatHourTime({ time: '2026-03-08T02:30' }, 'en-US')), '2:30 AM');
});

test('hourly cards across midnight keep their own wall-clock hours', () => {
  const labels = ['2026-11-09T23:00', '2026-11-10T00:00', '2026-11-10T01:00']
    .map(time => norm(formatHourTime({ time }, 'en-US')));
  assert.deepEqual(labels, ['11:00 PM', '12:00 AM', '1:00 AM']);
});

test('parseLocalWallClock anchors fields at UTC and rejects bad input', () => {
  assert.equal(parseLocalWallClock('2026-11-09T21:00').toISOString(), '2026-11-09T21:00:00.000Z');
  assert.equal(parseLocalWallClock('not a time'), null);
  assert.equal(parseLocalWallClock(undefined), null);
  assert.equal(formatViewingTime({ time: '' }, 'en-US'), '—');
  assert.equal(formatHourTime(undefined, 'en-US'), '—');
});

test('missing abbreviation omits the label rather than guessing', () => {
  assert.equal(norm(formatViewingTime({ time: '2026-11-09T21:00' }, 'en-US')), 'Mon, Nov 9, 9:00 PM');
});
