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

## ✅ KAPASİTE (ölçüldü, 2 GB RAM sınırıyla → diske taşma)
| Veri | Üret | Maskele | İstatistik | Agregasyon | Disk |
|---|---|---|---|---|---|
| 10M×20 (0.2B hücre) | 7.5s | 2.4s | 0.8s | 0.02s | 2.1 GB |
| 50M×20 (1.0B hücre) | 35s | 9.7s | 3.0s | 0.17s | 12.4 GB |
| **100M×20 (2.0B hücre)** | 72s | 24s | 9s | 0.43s | 33 GB |

→ 2 milyar hücre, sadece 2 GB RAM ile işlendi (disk-bound). Native motor hedefi karşılıyor.

## ✅ MOTOR UÇLARI TEST EDİLDİ (FastAPI TestClient + gerçek CSV)
health, process (col_stats + maskeleme), sql, aggregate (filtreli/filtresiz),
set-filters, sql-pivot, sample, download-processed — hepsi çalışıyor.
**Telefon/TCKN doğrulandı:** `05551000000` ve `10000000000` SQL'de birebir korunuyor
(baştaki sıfır + hassasiyet bozulmuyor); col_stats'ta isNumeric=False.
Ayrılmış kelime sütun adı (`"not"`) tırnaklı çalışıyor; hatalı SQL temiz 400 veriyor.

## ✅ TARAYICI ENTEGRASYONU TEST EDİLDİ (gerçek headless Chromium / Playwright)
Motor sayfayı sundu → api-bridge.js aktifleşti (BACKEND_ACTIVE=true, 🟢 rozet) →
`_backendProcess/_backendAggregate/_backendSetFilters` gerçek tarayıcıda çalıştı.
Telefon `05551000224` ve TCKN `10000000224` tarayıcıda da birebir korundu; ad
maskelendi (K**4). Uçtan uca akış doğrulandı.

İlk gerçek-veri denemesinde yine de göz atılacaklar (ortama bağlı olabilir):
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
