// Formats forecast times in the searched location's timezone, independent of the visitor's clock.
//
// The API's `time` fields are the location's local wall clock ("YYYY-MM-DDTHH:MM", no offset).
// `new Date()` would read such a string in the *visitor's* timezone, so instead the fields are
// split out, anchored at UTC, and formatted with timeZone 'UTC' — reproducing the wall clock exactly.

const LOCAL_TIME_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/;

function parseLocalWallClock(str) {
  const m = LOCAL_TIME_RE.exec(str || '');
  if (!m) return null;
  const [, y, mo, d, h, mi] = m.map(Number);
  return new Date(Date.UTC(y, mo - 1, d, h, mi));
}

function formatWallClock(str, options, locale) {
  const date = parseLocalWallClock(str);
  return date ? date.toLocaleString(locale, { ...options, timeZone: 'UTC' }) : '—';
}

// "Mon, Nov 9, 9:00 PM CST"
function formatViewingTime(hour, locale) {
  if (!hour || !parseLocalWallClock(hour.time)) return '—';
  const text = formatWallClock(hour.time, {
    weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  }, locale);
  return hour.tz_abbreviation ? `${text} ${hour.tz_abbreviation}` : text;
}

// "9:00 PM"
function formatHourTime(hour, locale) {
  return formatWallClock(hour && hour.time, { hour: 'numeric', minute: '2-digit' }, locale);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { parseLocalWallClock, formatViewingTime, formatHourTime };
}
