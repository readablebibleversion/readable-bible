(function () {
  var root = document.documentElement;
  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  // Theme toggle
  var toggle = document.querySelector('.theme-toggle');
  if (toggle) toggle.addEventListener('click', function () {
    var dark = root.dataset.theme
      ? root.dataset.theme === 'dark'
      : matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    store('theme', root.dataset.theme);
  });

  // Reader: jump menus and text size
  var reader = document.querySelector('.reader');
  if (reader && window.BOOKS) {
    var bookSel = reader.querySelector('.jump-book');
    var chSel = reader.querySelector('.jump-chapter');
    var cur = reader.dataset.book, curCh = +reader.dataset.chapter;
    BOOKS.forEach(function (b) {
      var o = new Option(b[0], b[1]);
      if (b[1] === cur) o.selected = true;
      bookSel.add(o);
    });
    function fillChapters(slug, selected) {
      var b = BOOKS.find(function (x) { return x[1] === slug; });
      chSel.innerHTML = '';
      for (var i = 1; i <= b[2]; i++) chSel.add(new Option('Chapter ' + i, i, false, i === selected));
      chSel.hidden = b[2] === 1;
    }
    fillChapters(cur, curCh);
    bookSel.addEventListener('change', function () { location.href = '/' + bookSel.value + '/1/'; });
    chSel.addEventListener('change', function () { location.href = '/' + bookSel.value + '/' + chSel.value + '/'; });

    var size = parseInt(getComputedStyle(root).getPropertyValue('--reader-size'), 10) || 20;
    reader.querySelectorAll('[data-size]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        size = Math.min(30, Math.max(14, size + 2 * +btn.dataset.size));
        root.style.setProperty('--reader-size', size + 'px');
        store('fontSize', size);
      });
    });

    setupComments(reader);

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && document.querySelector('.cp.open')) return;
      if (e.target.closest('input, select, textarea') || e.altKey || e.ctrlKey || e.metaKey) return;
      var link = e.key === 'ArrowLeft' ? reader.querySelector('a.prev') : e.key === 'ArrowRight' ? reader.querySelector('a.next') : null;
      if (link) location.href = link.href;
    });
  }

  // Verse comments: click a verse to read, post, and upvote anonymous comments.
  function setupComments(reader) {
    var book = reader.dataset.book, chapter = +reader.dataset.chapter;
    var bookName = reader.querySelector('.book-name').textContent;
    var comments = [], loaded = false, current = null;

    function session(key, fallback) {
      try { var v = sessionStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch (e) { return fallback; }
    }
    function saveSession(key, v) { try { sessionStorage.setItem(key, JSON.stringify(v)); } catch (e) {} }
    var sessionId = session('sessionId', null);
    if (!sessionId) {
      sessionId = crypto.randomUUID ? crypto.randomUUID() : 'xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx'.replace(/x/g, function () { return (Math.random() * 16 | 0).toString(16); });
      saveSession('sessionId', sessionId);
    }
    var voted = session('voted', []);
    var reported = session('reported', []);
    function visible(c) { return reported.indexOf(c.id) === -1; }

    function esc(s) { return s.replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
    function ago(iso) {
      var s = (Date.now() - new Date(iso)) / 1000;
      if (s < 60) return 'just now';
      var units = [[31536000, 'year'], [2592000, 'month'], [86400, 'day'], [3600, 'hour'], [60, 'minute']];
      for (var i = 0; i < units.length; i++) {
        var n = Math.floor(s / units[i][0]);
        if (n >= 1) return n + ' ' + units[i][1] + (n > 1 ? 's' : '') + ' ago';
      }
    }
    function api(body) {
      return fetch('/feedback', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
        .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || 'Something went wrong.'); return d; }); });
    }

    var panel = document.createElement('aside');
    panel.className = 'cp';
    panel.setAttribute('aria-label', 'Verse comments');
    panel.hidden = true;
    panel.innerHTML =
      '<div class="cp-head"><h2></h2><button type="button" class="cp-close" aria-label="Close">&times;</button></div>' +
      '<div class="cp-body"><blockquote class="cp-verse"></blockquote><p class="cp-status"></p><ol class="cp-list"></ol></div>' +
      '<form class="cp-form"><label class="hp">Leave this empty <input name="website" tabindex="-1" autocomplete="off"></label>' +
      '<textarea maxlength="1000" placeholder="Share a comment, question, or a clearer way to say this verse..." aria-label="Your comment" required></textarea>' +
      '<div class="row"><span>Posted anonymously</span><button type="submit">Post</button></div><p class="cp-error" role="alert"></p></form>';
    document.body.appendChild(panel);
    var list = panel.querySelector('.cp-list'), status = panel.querySelector('.cp-status');
    var form = panel.querySelector('form'), textarea = form.querySelector('textarea'), error = panel.querySelector('.cp-error');

    function updateBadges() {
      reader.querySelectorAll('.cbadge').forEach(function (b) { b.remove(); });
      var counts = {};
      comments.filter(visible).forEach(function (c) { counts[c.verse] = (counts[c.verse] || 0) + 1; });
      Object.keys(counts).forEach(function (v) {
        var el = document.getElementById('v' + v);
        if (!el) return;
        var b = document.createElement('span');
        b.className = 'cbadge';
        b.title = counts[v] + ' comment' + (counts[v] > 1 ? 's' : '');
        b.textContent = '\u{1F4AC} ' + counts[v];
        el.appendChild(b);
      });
    }

    function renderList() {
      if (current === null) return;
      if (!loaded) { status.textContent = 'Loading comments...'; list.innerHTML = ''; return; }
      var mine = comments.filter(function (c) { return c.verse === current && visible(c); })
        .sort(function (a, b) { return b.votes - a.votes || (b.created > a.created ? 1 : -1); });
      status.textContent = mine.length ? '' : 'No comments yet. Be the first to share a thought on this verse.';
      list.innerHTML = mine.map(function (c) {
        var has = voted.indexOf(c.id) !== -1;
        return '<li><button type="button" class="cp-vote' + (has ? ' voted' : '') + '" data-id="' + c.id + '"' + (has ? ' disabled aria-pressed="true"' : '') +
          ' aria-label="Upvote"><span class="arrow">&#9650;</span>' + c.votes + '</button>' +
          '<div><p class="cp-text">' + esc(c.text) + '</p><div class="cp-meta">Anonymous &middot; ' + ago(c.created) +
            ' &middot; <button type="button" class="cp-report" data-id="' + c.id + '">Report</button></div></div></li>';
      }).join('');
    }

    function load() {
      return fetch('/feedback?book=' + encodeURIComponent(book) + '&chapter=' + chapter)
        .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
        .then(function (d) { comments = d.comments || []; loaded = true; updateBadges(); renderList(); })
        .catch(function () { loaded = true; comments = []; status.textContent = 'Comments are unavailable right now.'; list.innerHTML = ''; });
    }

    function open(verseEl) {
      var v = +verseEl.id.slice(1);
      current = v;
      reader.querySelectorAll('.verse.selected').forEach(function (el) { el.classList.remove('selected'); });
      verseEl.classList.add('selected');
      var clone = verseEl.cloneNode(true);
      clone.querySelectorAll('.vnum, .fn-ref, .cbadge').forEach(function (n) { n.remove(); });
      clone.querySelectorAll('br').forEach(function (n) { n.replaceWith('\n'); });
      panel.querySelector('h2').textContent = bookName + ' ' + chapter + ':' + v;
      panel.querySelector('.cp-verse').textContent = clone.textContent.trim();
      error.textContent = '';
      panel.hidden = false;
      requestAnimationFrame(function () { panel.classList.add('open'); });
      renderList();
    }
    function close() {
      panel.classList.remove('open');
      reader.querySelectorAll('.verse.selected').forEach(function (el) { el.classList.remove('selected'); });
      current = null;
      setTimeout(function () { if (!panel.classList.contains('open')) panel.hidden = true; }, 250);
    }

    reader.querySelector('.text').addEventListener('click', function (e) {
      if (e.target.closest('a')) return;
      var verseEl = e.target.closest('.verse');
      if (verseEl && !(window.getSelection && String(window.getSelection()).length)) open(verseEl);
    });
    panel.querySelector('.cp-close').addEventListener('click', close);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && panel.classList.contains('open')) close(); });

    list.addEventListener('click', function (e) {
      var rep = e.target.closest('.cp-report');
      if (rep) {
        if (!confirm('Report this comment as rude or inappropriate? It will be hidden for you, and removed for everyone after several reports.')) return;
        var rid = rep.dataset.id;
        rep.disabled = true;
        api({ action: 'report', book: book, chapter: chapter, id: rid }).then(function () {
          reported.push(rid);
          saveSession('reported', reported);
          updateBadges();
          renderList();
          status.textContent = 'Thanks. The comment was reported.';
        }).catch(function () { rep.disabled = false; });
        return;
      }
      var btn = e.target.closest('.cp-vote');
      if (!btn || btn.disabled) return;
      var id = btn.dataset.id;
      btn.disabled = true;
      api({ action: 'vote', book: book, chapter: chapter, id: id, session: sessionId }).then(function (d) {
        comments.forEach(function (c) { if (c.id === id) c.votes = d.votes; });
        voted.push(id);
        saveSession('voted', voted);
        renderList();
      }).catch(function () { btn.disabled = false; });
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var text = textarea.value.trim();
      if (text.length < 2) { error.textContent = 'Please write a little more.'; return; }
      var btn = form.querySelector('button');
      btn.disabled = true;
      error.textContent = '';
      api({ action: 'comment', book: book, chapter: chapter, verse: current, text: text, website: form.website.value })
        .then(function (d) {
          if (d.comment) comments.push(d.comment);
          textarea.value = '';
          updateBadges();
          renderList();
        })
        .catch(function (err) { error.textContent = err.message; })
        .then(function () { btn.disabled = false; });
    });

    load();
  }

  // Library: filter books
  var filter = document.querySelector('.library .filter');
  if (filter) filter.addEventListener('input', function () {
    var q = filter.value.trim().toLowerCase();
    document.querySelectorAll('.book').forEach(function (el) {
      var match = !q || el.querySelector('summary span').textContent.toLowerCase().indexOf(q) !== -1;
      el.classList.toggle('hidden', !match);
      el.open = !!q && match;
    });
  });

  // Search
  var q = document.getElementById('q');
  if (q) {
    var status = document.querySelector('.search-status');
    var list = document.querySelector('.results');
    var data = null, loading = null, timer;
    function load() {
      if (!loading) loading = fetch('/assets/search.json').then(function (r) { return r.json(); }).then(function (d) { data = d; });
      return loading;
    }
    function escapeHtml(s) { return s.replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
    function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
    function slugify(s) { return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''); }

    function tryReference(text) {
      var m = text.trim().match(/^(\d?\s*[a-z][a-z ]*?)\s*(\d+)(?:\s*:\s*(\d+))?$/i);
      if (!m) return null;
      var name = slugify(m[1]);
      var b = BOOKS.find(function (x) { return x[1] === name || x[1].indexOf(name) === 0 || (name === 'psalm' && x[1] === 'psalms'); });
      if (!b || +m[2] > b[2]) return null;
      return '/' + b[1] + '/' + m[2] + '/' + (m[3] ? '#v' + m[3] : '');
    }

    function run() {
      var text = q.value.trim();
      try { history.replaceState(null, '', text ? '?q=' + encodeURIComponent(text) : location.pathname); } catch (e) {}
      list.innerHTML = '';
      if (text.length < 2) { status.textContent = ''; return; }
      var ref = tryReference(text);
      status.textContent = 'Searching...';
      load().then(function () {
        var re = new RegExp(escapeRe(text), 'gi');
        var hits = [];
        for (var i = 0; i < data.length && hits.length < 200; i++) {
          re.lastIndex = 0;
          if (re.test(data[i][2])) hits.push(data[i]);
        }
        var html = '';
        if (ref) html += '<li><a href="' + ref + '">Go to ' + escapeHtml(text) + ' &rarr;</a></li>';
        html += hits.map(function (h) {
          return '<li><a href="' + h[1] + '">' + escapeHtml(h[0]) + '</a><p>' +
            escapeHtml(h[2]).replace(new RegExp(escapeRe(escapeHtml(text)), 'gi'), '<mark>$&</mark>') + '</p></li>';
        }).join('');
        list.innerHTML = html;
        status.textContent = hits.length === 200 ? 'Showing the first 200 verses.' : hits.length + ' verse' + (hits.length === 1 ? '' : 's') + ' found.';
      }).catch(function () { status.textContent = 'Search could not load. Please try again.'; });
    }
    q.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 250); });
    q.form.addEventListener('submit', function (e) {
      e.preventDefault();
      var ref = tryReference(q.value);
      if (ref) location.href = ref; else run();
    });
    var initial = new URLSearchParams(location.search).get('q');
    if (initial) { q.value = initial; run(); }
    q.focus();
  }
})();
