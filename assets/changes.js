(function(){
  // Changes viewer initialization - expects window.__HISTORICAL_DATES and window.__HISTORICAL_DATA
  function escapeHtml(s) { return ('' + (s || '')).replace(/[&<>\"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }

  function initDatePicker(dates) {
    var dateInput = document.getElementById('changes-date-picker');
    if (!dateInput) return;
    if (typeof flatpickr !== 'undefined') {
      try {
        flatpickr(dateInput, { dateFormat: 'Y-m-d', enable: dates, defaultDate: dates[0] || null, disableMobile: true });
      } catch (e) {
        dateInput.type = 'date';
        dateInput.min = dates[dates.length-1]; dateInput.max = dates[0]; dateInput.value = dates[0];
      }
    } else {
      dateInput.type = 'date';
      dateInput.min = dates[dates.length-1]; dateInput.max = dates[0]; dateInput.value = dates[0];
    }
  }

  function renderSelectedDate(dateStr) {
    var target = document.getElementById('selected-date-details');
    var data = (window.__HISTORICAL_DATA || {})[dateStr] || [];
    if (!data.length) {
      target.style.display = 'block';
      target.innerHTML = '<div style="padding:12px;color:#6b7280">No data for ' + dateStr + '</div>';
      return;
    }
    var html = '<h4>Snapshot: ' + dateStr + ' (' + data.length + ' broken links)</h4>';
    html += '<table id="selected-date-table" class="display" style="width:100%"><thead><tr><th>Region</th><th>Status</th><th>URL</th><th>Error Message</th><th>Timestamp</th></tr></thead><tbody>';
    data.forEach(function(r){ html += '<tr><td>'+escapeHtml(r.Region||'')+'</td><td>'+escapeHtml(''+r.Status)+'</td><td><a href="'+escapeHtml(r.URL||'')+'" target="_blank">'+escapeHtml(r.URL||'')+'</a></td><td>'+escapeHtml(r.Error_Message||'')+'</td><td>'+escapeHtml(r.Timestamp||'')+'</td></tr>'; });
    html += '</tbody></table>';
    target.style.display = 'block';
    target.innerHTML = html;
    try { $('#selected-date-table').DataTable({ pageLength: 10 }); } catch(e) {}
  }

  function buildSevenDaySummary() {
    var wrap = document.getElementById('seven-day-summary-table');
    if (!wrap) return;
    var dates = (window.__HISTORICAL_DATES || []).slice();
    dates.sort(function(a,b){ return (new Date(b)) - (new Date(a)); });
    if (!dates.length) { wrap.innerHTML = '<div style="padding:12px;color:#6b7280">No historical snapshots available.</div>'; return; }

    var rows = [];
    rows.push('<table style="width:100%"><thead><tr><th>Date</th><th>AU Added</th><th>AU Removed</th><th>NZ Added</th><th>NZ Removed</th><th>Details</th></tr></thead><tbody>');
    for (var i=0;i<Math.min(7, dates.length); i++) {
      var d = dates[i];
      var curr = (window.__HISTORICAL_DATA || {})[d] || [];
      var prev = (i+1<dates.length) ? (window.__HISTORICAL_DATA || {})[dates[i+1]] || [] : [];
      var sep = '|||';
      var currSet = new Set(); var prevSet = new Set();
      curr.forEach(function(it){ currSet.add((it.Region||'')+sep+(it.URL||'')); });
      prev.forEach(function(it){ prevSet.add((it.Region||'')+sep+(it.URL||'')); });
      var added=[], removed=[]; currSet.forEach(function(k){ if (!prevSet.has(k)) added.push(k); }); prevSet.forEach(function(k){ if (!currSet.has(k)) removed.push(k); });
      var aAU=0,aNZ=0,rAU=0,rNZ=0;
      added.forEach(function(k){ var p=k.split(sep); if ((p[0]||'').toUpperCase()==='AU') aAU++; else if ((p[0]||'').toUpperCase()==='NZ') aNZ++; });
      removed.forEach(function(k){ var p=k.split(sep); if ((p[0]||'').toUpperCase()==='AU') rAU++; else if ((p[0]||'').toUpperCase()==='NZ') rNZ++; });
      rows.push('<tr class="summary-row" data-date="'+d+'"><td>'+d+'</td><td>'+aAU+'</td><td>'+rAU+'</td><td>'+aNZ+'</td><td>'+rNZ+'</td><td><button class="details-btn" data-date="'+d+'">Toggle</button></td></tr>');
      rows.push('<tr id="summary-'+d+'-details" class="summary-details" style="display:none"><td colspan="6"></td></tr>');
    }
    rows.push('</tbody></table>');
    wrap.innerHTML = rows.join('');

    wrap.querySelectorAll('.details-btn').forEach(function(btn){
      btn.addEventListener('click', function(){
        var d = this.getAttribute('data-date');
        var detailRow = document.getElementById('summary-'+d+'-details');
        if (!detailRow) return;
        if (detailRow.style.display === 'table-row') { detailRow.style.display='none'; return; }
        var dates = (window.__HISTORICAL_DATES || []).slice(); dates.sort(function(a,b){ return (new Date(b)) - (new Date(a)); });
        var idx = dates.indexOf(d);
        var prevDate = (idx+1<dates.length) ? dates[idx+1] : null;
        var curr = (window.__HISTORICAL_DATA || {})[d] || [];
        var prev = prevDate ? (window.__HISTORICAL_DATA || {})[prevDate] || [] : [];
        var sep = '|||';
        var currSet = new Set(); var prevSet = new Set();
        curr.forEach(function(it){ currSet.add((it.Region||'') + sep + (it.URL||'')); });
        prev.forEach(function(it){ prevSet.add((it.Region||'') + sep + (it.URL||'')); });
        var addedList = [], removedList = [];
        currSet.forEach(function(k){ if (!prevSet.has(k)) addedList.push(k); });
        prevSet.forEach(function(k){ if (!currSet.has(k)) removedList.push(k); });
        function renderList(arr){ if (!arr.length) return '<div style="padding:10px;color:#6b7280">No items</div>'; var o = '<ul style="padding-left:16px">'; arr.forEach(function(k){ var p = k.split(sep); var region = escapeHtml(p[0] || ''); var url = escapeHtml(p.slice(1).join(sep) || ''); o += '<li><strong>' + region + '</strong>: <a href="' + url + '" target="_blank">' + url + '</a></li>'; }); o += '</ul>'; return o; }
        var html = '<div style="display:flex;gap:18px;flex-wrap:wrap">';
        html += '<div style="flex:1;min-width:260px"><h4 style="margin-top:0">Added</h4>' + renderList(addedList) + '</div>';
        html += '<div style="flex:1;min-width:260px"><h4 style="margin-top:0">Removed</h4>' + renderList(removedList) + '</div>';
        html += '</div>';
        detailRow.cells[0].innerHTML = html;
        detailRow.style.display = 'table-row';
      });
    });
  }

  function initChangeTables() {
    var changesTables = ['#yesterday-added-table', '#yesterday-removed-table', '#week-added-table', '#week-removed-table'];
    changesTables.forEach(function(tableId){
      if (!$(tableId).length) return;
      try { $(tableId).DataTable({ pageLength: 50, orderCellsTop: true, fixedHeader: true, order: [[2, 'asc']] }); }
      catch (err) { try { $(tableId).DataTable({ pageLength: 50, orderCellsTop: true, fixedHeader: true, order: [[2, 'asc']] }); } catch(e){} }
    });
  }

  document.addEventListener('DOMContentLoaded', function(){
    var dates = (window.__HISTORICAL_DATES || []).slice(); dates.sort(function(a,b){ return (new Date(b)) - (new Date(a)); });
    if (dates.length) {
      initDatePicker(dates);
      document.getElementById('changes-date-picker').value = dates[0];
      buildSevenDaySummary();
      initChangeTables();
    }

    var showBtn = document.getElementById('show-date-btn');
    if (showBtn) showBtn.addEventListener('click', function(){ var dt = document.getElementById('changes-date-picker').value; if (!dt) { dt = (window.__HISTORICAL_DATES || [])[0]; document.getElementById('changes-date-picker').value = dt; } renderSelectedDate(dt); });

    var downloadBtn = document.getElementById('download-snapshot-btn');
    if (downloadBtn) downloadBtn.addEventListener('click', function(){ var dt = document.getElementById('changes-date-picker').value || (window.__HISTORICAL_DATES || [])[0]; var data = (window.__HISTORICAL_DATA || {})[dt] || []; if (!data || !data.length) { alert('No data available for ' + dt); return; } var rows = [['Region','Status','URL','Error_Message','Timestamp']]; data.forEach(function(r){ rows.push([r.Region, ''+r.Status, r.URL, r.Error_Message, r.Timestamp]); }); var csvLines = rows.map(function(r){ return r.map(function(c){ return '"' + (''+(c||'')).replace(/"/g,'""') + '"'; }).join(','); }).join('\n'); var blob = new Blob([csvLines], { type: 'text/csv;charset=utf-8;' }); var url = URL.createObjectURL(blob); var a = document.createElement('a'); a.href = url; a.download = 'snapshot_' + dt + '.csv'; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url); });
  });

})();
