# Fund Manager Workstation v2

Bu sürüm eski zinciri kaldırır:
- Excel
- VBA
- Google Sheets
- Apps Script

Günlük kullanım için bunların hiçbirine ihtiyaç yoktur.

Portföy yöneticisi sadece web sitesine girer ve soldaki tuşlarla veriyi yeniler.

## Bu sürümde gerçek entegrasyon
- **ETF ve ETF tarihçesi**: Yahoo Finance
- **TEFAS watchlist**: TEFAS fon sayfaları
- **Repo / TPP TRY referansı**: kamuya açık resmi sayfalar

## Bu sürümde seed kalan alanlar
- Kamuya açık canlı executable feed'i olmayan bazı **local bond / eurobond** satırları
- Bunlar arayüz, mandate fit ve portfolio lab çalışsın diye sistemde kalır
- Lisanslı veri kaynağı eklenince aynı tablo yapısına bağlanabilir

## Çalıştırma
Yerelde:
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit deploy
Eğer repo yapın şu an aşağıdaki gibiyse:
- `README.md`
- `ultimate_fund_screener/`

Streamlit'te **Main file path** alanına şunu yaz:
```text
ultimate_fund_screener/app.py
```

## Kullanım
1. Uygulama açılınca soldan **Veritabanını sıfırla ve temel veriyi yeniden kur** tuşuna bir kere bas.
2. Sonra **Tüm gerçek / kamu verisini yenile** tuşuna bas.
3. Screener, Compare ve Portfolio Lab sekmelerini kullan.

## Senin yapman gerekenler
Sadece şunları yap:
1. Bu klasördeki dosyalarla repodaki `ultimate_fund_screener` klasörünü değiştir.
2. GitHub'a commit et.
3. Streamlit Cloud'da app'i yeniden deploy et.

## Teknik not
Bu sürümde veri tabanı yine projenin içindeki SQLite dosyasıdır. Ayrı database sunucusu gerekmez.
