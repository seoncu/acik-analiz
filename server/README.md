# Açık Analiz — Native Motor (büyük veri, opsiyonel)

Tarayıcı modu çoğu kullanıcı için yeterlidir (kurulum yok). Bu motor **yalnızca
çok büyük veri** (yüz milyonlarca–milyarlarca hücre) için. Native DuckDB ile
disk-destekli çalışır → RAM ile değil, disk ile sınırlıdır.

## Kullanıcı nasıl çalıştırır
1. Başlatıcıyı indir: `AcikAnaliz-Baslat.command` (macOS) / `AcikAnaliz-Baslat.bat` (Windows).
   (Açık Analiz açılış ekranındaki "🚀 Çok büyük veri için masaüstü motoru" bölümünden.)
2. Çift tıkla. (macOS ilk seferde: sağ tık → Aç. Windows: SmartScreen → Yine de çalıştır.)
3. Motor açılır; tarayıcı `http://127.0.0.1:8765` adresinde otomatik açılır.
   Sağ altta **🟢 Motor aktif** rozeti görünür.

İlk açılışta internet gerekir (uv + Python 3.12 + kütüphaneler + güncel arayüz indirilir).
Sonraki açılışlar hızlı; her açılışta GitHub'dan en güncel sürüm çekilir.

## Güncelleme yönetimi
`git push` → herkes bir sonraki açılışta otomatik en güncel sürümü alır.
(Başlatıcı dosyası nadiren değişir; değişirse yeniden paylaşılır.)

## Mimari
- `engine.py` — FastAPI + DuckDB. Arayüzü (index.html + api-bridge.js) **aynı
  kökenden** (127.0.0.1:8765) sunar → mixed-content engeli yok.
- `api-bridge.js` — frontend↔motor köprüsü. **Yalnızca 127.0.0.1/localhost'ta
  aktif**; canlı HTTPS sitede uykuda (tarayıcı-only deneyimi etkilenmez).
- `requirements.txt` — sabit sürümler.

## ⚠️ TEST DURUMU (geliştirici notu)
Bu motor uçtan uca **henüz test edilmedi** (sunucu+tarayıcı+gerçek veri gerekir).
Python/JS sözdizimi doğrulandı. Gerçek veriyle test ederken kontrol edilecekler:
- `/api/health` 200 dönüyor mu, rozet görünüyor mu?
- Dosya yükle → işle: `/api/process` col_stats/sample doğru mu? (Adım 6)
- Dashboard grafikleri `/api/aggregate` ile geliyor mu?
- SQL sekmesi `/api/sql` ile çalışıyor mu? Pivot `/api/sql-pivot`?
- Filtreler `/api/set-filters` sonrası agregasyona yansıyor mu?
- "İşlenmiş veriyi indir" `/api/download-processed` çalışıyor mu?
- xlsx girdi: DuckDB `excel` eklentisi gerekebilir (read_xlsx). CSV/TSV native.

Olası ilk-tur düzeltmeler: dönüş şekli uyuşmazlıkları (özellikle aggregate/sample
kontratları), xlsx okuma, filtre nesnesi alanları. Sorun çıkan ucu izole edip
düzeltmek yeterli — köprüdeki tanımsız fonksiyonlarda frontend zaten JS'e düşer.
