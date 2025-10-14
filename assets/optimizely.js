(function(){
  // Optimizely UI wiring. Assumes window.__OPTIMIZELY_COMBINED is set before this script runs.
  function initOptimizely() {
    const container = document.getElementById('optly-container');
    if (!container) return;

    const tabs = Array.from(container.querySelectorAll('.optly-tab'));
    const tabContents = Array.from(container.querySelectorAll('.optly-tab-content'));
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const targetId = tab.getAttribute('data-target');
        tabs.forEach(t => t.classList.remove('active'));
        tabContents.forEach(content => content.classList.remove('active'));
        tab.classList.add('active');
        const target = container.querySelector('#' + targetId);
        if (target) target.classList.add('active');
      });
    });

    container.querySelectorAll('.optly-collapsible').forEach(button => {
      button.addEventListener('click', () => {
        const targetId = button.getAttribute('data-target');
        const content = container.querySelector('#' + targetId);
        button.classList.toggle('active');
        if (content) content.classList.toggle('active');
      });
    });

    container.querySelectorAll('.optly-row-header').forEach(header => {
      header.addEventListener('click', () => {
        const targetId = header.getAttribute('data-target');
        const content = container.querySelector('#' + targetId);
        const icon = header.querySelector('.optly-expand-icon');
        if (!content || !icon) return;
        if (content.classList.contains('expanded')) {
          content.classList.remove('expanded'); icon.classList.remove('expanded'); header.classList.remove('expanded');
        } else {
          content.classList.add('expanded'); icon.classList.add('expanded'); header.classList.add('expanded');
        }
      });
    });

    container.querySelectorAll('.optly-json-key.optly-has-children').forEach(key => {
      key.addEventListener('click', (e) => {
        e.stopPropagation();
        const targetId = key.getAttribute('data-target');
        const node = container.querySelector('#' + targetId);
        const icon = key.querySelector('.optly-expand-icon');
        if (!node || !icon) return;
        if (node.classList.contains('collapsed')) { node.classList.remove('collapsed'); icon.textContent = '▼'; }
        else { node.classList.add('collapsed'); icon.textContent = '▶'; }
      });
    });

    // Search/filter
    const searchInput = container.querySelector('#optly-search-input');
    const clearButton = container.querySelector('#optly-search-clear');

    const filterRows = () => {
      const term = (searchInput.value || '').toLowerCase().trim();
      if (clearButton) { clearButton.classList.toggle('visible', term.length > 0); }
      const rows = Array.from(container.querySelectorAll('.optly-table-row'));
      rows.forEach(row => {
        const titleHay = (row.getAttribute('data-search-title') || '').toLowerCase();
        const metaHay = (row.getAttribute('data-search-meta') || '').toLowerCase();
        if (!term || titleHay.includes(term) || metaHay.includes(term)) row.classList.remove('hidden'); else row.classList.add('hidden');
      });
      container.querySelectorAll('.optly-expandable-table').forEach(table => {
        const visibleRows = table.querySelectorAll('.optly-table-row:not(.hidden)');
        let message = table.querySelector('.optly-no-results');
        if (term && visibleRows.length === 0) {
          if (!message) { message = document.createElement('div'); message.className='optly-no-results'; message.textContent = 'No results found for "' + searchInput.value + '"'; table.appendChild(message); }
          else { message.textContent = 'No results found for "' + searchInput.value + '"'; }
        } else if (message) { message.remove(); }
      });
    };

    if (searchInput) {
      searchInput.addEventListener('input', filterRows);
      searchInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') e.preventDefault(); });
      filterRows();
    }
    if (clearButton) { clearButton.addEventListener('click', function(){ if (searchInput) { searchInput.value=''; filterRows(); searchInput.focus(); } }); }

    // Export combined Optimizely data to CSV
    const exportBtn = container.querySelector('#optly-export-csv');
    if (exportBtn) {
      exportBtn.addEventListener('click', function(){
        try {
          const combined = window.__OPTIMIZELY_COMBINED || {};
          const rows = [];
          const header = ['type','region','id','key','name','status','payload']; rows.push(header);
          function pushRow(type, item) { const region = item && item.region ? String(item.region) : ''; const id = (item && item.id != null) ? String(item.id) : ((item && item['id'] != null) ? String(item['id']) : ''); const key = (item && item.key != null) ? String(item.key) : ''; const name = (item && item.name != null) ? String(item.name) : ((item && item.title != null) ? String(item.title) : ''); const status = (item && item.status != null) ? String(item.status) : ''; var payload = ''; try { payload = JSON.stringify(item); } catch (err) { payload = ''; } rows.push([type, region, id, key, name, status, payload]); }
          (combined.events || []).forEach(ev => pushRow('event', ev));
          (combined.featureFlags || []).forEach(ff => pushRow('flag', ff));
          (combined.experiments || []).forEach(ex => pushRow('experiment', ex));
          const csvLines = rows.map(r => r.map(c => '"' + ('' + (c || '')).replace(/"/g,'""') + '"').join(','));
          const csv = csvLines.join('\n');
          const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
          const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'optimizely_export.csv'; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
        } catch(e) { console.error('Export failed', e); alert('Export failed: ' + e); }
      });
    }
  }

  document.addEventListener('DOMContentLoaded', initOptimizely);
})();
