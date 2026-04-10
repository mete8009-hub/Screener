# Fund Manager Workstation

Bu proje, eski "nakit park motoru" mantığını daha geniş bir **fon yöneticisi iş istasyonu** yapısına çevirir.

## Bu sürümde ne var?
- Tek Streamlit uygulaması
- Tek yerel SQLite veritabanı
- Screener
- Compare ekranı
- Portfolio Lab
- Mandate fit kontrolü
- Tek tuşla veritabanını sıfırlayıp tekrar kurma

## Eski karmaşık zincir yok
Bu sürümde şunlar zorunlu değil:
- Excel
- VBA
- Google Sheets
- Apps Script

Hepsi tek proje klasörü içinde çalışır.

## Klasör yapısı
- `app.py` → ana Streamlit uygulaması
- `screener/` → veri tabanı, seed, metrik ve repository kodları
- `data/seed_instruments.csv` → demo bond / eurobond / ETF / fon evreni
- `data/legacy/` → eski projeden gelen mevcut CSV dosyaları
- `data/fund_manager_workstation.db` → uygulamanın kendi veritabanı

## İlk çalıştırma
```bash
pip install -r requirements.txt
streamlit run app.py
```

Uygulama açılınca veritabanı yoksa otomatik oluşturur ve seed verileri yükler.

## Bu sürüm nasıl düşünülmeli?
Bu sürüm **çalışan temel ürün omurgasıdır**.
Aşağıdakiler hazırdır:
- yeni veri şeması
- tek web arayüzü
- mandate bazlı uygunluk kontrolü
- portföy sepeti kurup geçmiş performans analizi

Aşağıdakiler sonraki iterasyonda gerçek veriyle güçlendirilmeli:
- gerçek ETF tarihsel serileri
- gerçek tahvil / eurobond fiyat geçmişi
- TEFAS kategori bazlı tam otomasyon
- tek tık güncel veri çekme connector'ları

## Kullanıcı için basit iş akışı
1. Uygulamayı aç.
2. Sol menüden mandate seç.
3. Screener ekranında filtrele.
4. Compare ekranında enstrümanları karşılaştır.
5. Portfolio Lab ekranında ağırlık verip sepet kur.
6. Korelasyon, hedge oranı, drawdown ve risk metriklerini gör.

## Gerçek veri eklemek istediğinde
İlk aşamada sadece şu dosyaları güncellemen yeterli:
- `data/legacy/instruments_master.csv`
- `data/legacy/market_quotes.csv`
- `data/legacy/portfolio_rules.csv`

Sonra uygulamada:
- **"Veritabanını sıfırla ve yeniden kur"** tuşuna bas.

Bu kadar.
