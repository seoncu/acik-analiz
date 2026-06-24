/* ============================================================
   Açık Analiz — Frontend ↔ Native Motor köprüsü (api-bridge.js)
   ------------------------------------------------------------
   GÜVENLİK: Bu dosya yalnızca sayfa YEREL motor altında
   (http://127.0.0.1 / localhost) sunulduğunda aktifleşir.
   GitHub Pages (https) üzerinde TAMAMEN UYKUDADIR — canlı
   tarayıcı-only deneyimi hiçbir şekilde etkilenmez.
   ============================================================ */
(function(){
  'use strict';
  var loc = window.location;
  var isLocal = (loc.protocol === 'http:') &&
                (loc.hostname === '127.0.0.1' || loc.hostname === 'localhost');
  if (!isLocal) {
    // Canlı/HTTPS sayfa → motor kullanılmıyor. Köprü uykuda. Hiçbir şey yapma.
    return;
  }

  var API = loc.origin; // motor sayfayı kendisi sunduğundan aynı köken
  window._API_BASE = API;

  function post(path, body, isForm){
    var opts = { method:'POST' };
    if (isForm) { opts.body = body; }
    else { opts.headers = {'Content-Type':'application/json'}; opts.body = JSON.stringify(body||{}); }
    return fetch(API + path, opts).then(function(r){
      return r.json().then(function(j){ if(!r.ok || (j && j.error)) throw new Error((j&&j.error)||('HTTP '+r.status)); return j; });
    });
  }
  function get(path){
    return fetch(API + path).then(function(r){ return r.json(); });
  }

  // ---- Sağlık kontrolü: motor ayakta mı? ----
  function probe(){
    return fetch(API + '/api/health', { signal: (AbortSignal.timeout?AbortSignal.timeout(3000):undefined) })
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        if (d && d.status === 'ok') {
          window._BACKEND_ACTIVE = true;
          window._BACKEND_INFO = d;
          _injectBadge(d);
          if (typeof window._updateEngineModeUI === 'function') { try{window._updateEngineModeUI();}catch(e){} }
        }
      })
      .catch(function(){ /* motor yok → sessiz, tarayıcı modu */ });
  }

  // ---- Küçük "motor aktif" rozeti (index.html'deki kaldırılmış UI'a bağımlı değil) ----
  function _injectBadge(d){
    if (document.getElementById('_engineBadge')) return;
    var b = document.createElement('div');
    b.id = '_engineBadge';
    b.style.cssText = 'position:fixed;right:12px;bottom:12px;z-index:10050;background:#065f46;color:#fff;padding:6px 12px;border-radius:20px;font-size:12px;font-weight:600;box-shadow:0 4px 12px rgba(0,0,0,.2)';
    b.textContent = '🟢 Motor aktif — DuckDB (' + (d.duckdb||'') + ')';
    if (document.body) document.body.appendChild(b);
    else window.addEventListener('DOMContentLoaded', function(){ document.body.appendChild(b); });
  }

  // ============================================================
  //  window._backend* — frontend'in beklediği köprü fonksiyonları
  //  (tanımlı olanlar motoru kullanır; tanımsız bırakılanlarda
  //   frontend otomatik JS/örneklem yedeğine düşer)
  // ============================================================

  // İşle + maskele (tek dosya). file: File, maskConfig:{col:'none|hash|partial|remove'}, delimiter
  window._backendProcess = function(file, maskConfig, delimiter){
    var fd = new FormData();
    fd.append('file', file, file.name || 'data.csv');
    fd.append('mask_config', JSON.stringify(maskConfig||{}));
    fd.append('delimiter', delimiter||',');
    return post('/api/process', fd, true);
  };

  // İşle + maskele (çoklu dosya — sunucuda birleştir)
  window._backendProcessMulti = function(files, maskConfig, delimiter, labels){
    var fd = new FormData();
    for (var i=0;i<files.length;i++){ fd.append('files', files[i], files[i].name || ('data'+i+'.csv')); }
    fd.append('mask_config', JSON.stringify(maskConfig||{}));
    fd.append('delimiter', delimiter||',');
    fd.append('labels', JSON.stringify(labels||[]));
    return post('/api/process-multi', fd, true);
  };

  // Yalnızca yükle (maskeleme yok) — bazı yollar bunu çağırır
  window._backendUpload = function(file){
    var fd = new FormData();
    fd.append('file', file, file.name || 'data.csv');
    return post('/api/upload', fd, true);
  };

  // Aktif filtreleri sunucuya bildir (sonraki sorgular bunu uygular)
  window._backendSetFilters = function(filtersObj){
    return post('/api/set-filters', { filters: filtersObj||{} });
  };

  // X kırılımına göre toplulaştırma (grafikler için)
  window._backendAggregate = function(xCol, yCols, aggType, sortMode, limit, extra){
    return post('/api/aggregate', {
      x: xCol, y: yCols||[], agg: aggType||'count',
      sort: sortMode||'desc', limit: limit||15, extra: extra||''
    });
  };

  // Filtre uygulanmış kolon istatistikleri
  window._backendFilteredStats = function(filtersObj){
    return post('/api/filtered-stats', { filters: filtersObj||{} });
  };

  // Örneklem satırları (n satır, ofset) — {rows:[{col:val}]}
  window._backendSample = function(n, offset){
    return post('/api/sample', { n: n||1000, offset: offset||0 });
  };

  // İşlenmiş veriyi indir (csv/xlsx) — sunucudan dosya akışı
  window._backendDownloadProcessed = function(format){
    var url = API + '/api/download-processed?format=' + encodeURIComponent(format||'csv');
    var a = document.createElement('a');
    a.href = url; a.download = 'maskelenmis_veri.' + (format==='xlsx'?'xlsx':'csv');
    document.body.appendChild(a); a.click();
    setTimeout(function(){ document.body.removeChild(a); }, 1500);
    return Promise.resolve({ ok:true });
  };

  // Sayfa yüklenince motoru yokla
  if (document.readyState === 'complete' || document.readyState === 'interactive') probe();
  else window.addEventListener('DOMContentLoaded', probe);
})();
