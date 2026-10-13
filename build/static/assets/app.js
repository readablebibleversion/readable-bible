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

    document.addEventListener('keydown', function (e) {
      if (e.target.closest('input, select, textarea') || e.altKey || e.ctrlKey || e.metaKey) return;
      var link = e.key === 'ArrowLeft' ? reader.querySelector('a.prev') : e.key === 'ArrowRight' ? reader.querySelector('a.next') : null;
      if (link) location.href = link.href;
    });
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
