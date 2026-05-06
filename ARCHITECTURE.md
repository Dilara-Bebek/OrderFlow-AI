## OrderFlow AI – Sistem Mimarisi

### 1. Genel Vizyon

OrderFlow AI, işletmelerin WhatsApp üzerinden aldıkları siparişleri **otonom şekilde yöneterek** manuel operasyonel yükü en az **%50 oranında azaltmayı** hedefleyen bir yapay zeka destekli sipariş yönetim sistemidir.  
Sistem; sipariş alma, sipariş doğrulama, müşteriyle yazışma, stok/ürün kontrolü ve işletme sahibine özet raporlar sunma süreçlerini uçtan uca otomatikleştirerek:
- **Zaman kazancı** (operasyon ekibinin tekrar eden yazışmalardan kurtulması),
- **Hata oranının düşürülmesi** (yanlış ürün, yanlış adres, eksik bilgi),
- **Operasyonel şeffaflık** (dashboard üzerinden anlık görünürlük),
- **Ölçeklenebilirlik** (artan mesaj hacmine insan kaynağından bağımsız cevap verebilme)
sağlar.

Bu hedefe ulaşmak için sistem, **minimum insan müdahalesiyle yüksek doğrulukta sipariş işleme** prensibiyle tasarlanmıştır. İnsan müdahalesi yalnızca:
- Yeni/karmaşık senaryoların onaylanması,
- Modelin eğitilmesi için geri bildirim verme,
- İş kuralları ve kampanya tanımları gibi üst seviye konfigürasyonlar
alanlarında gereklidir.

### 2. Yüksek Seviye Mimari Genel Bakış

Sistem üç ana katmandan oluşur:
- **Sunum Katmanı (UI Layer)**  
  - `WhatsApp Simulation UI` (Streamlit)  
  - `Business Owner Admin Dashboard` (Streamlit)
- **Uygulama ve Veri Katmanı (Application & Data Layer)**  
  - Sipariş iş akışı orkestrasyonu  
  - İş kuralları ve doğrulamalar  
  - SQLite veri tabanı (Müşteriler, Ürünler, Siparişler)
- **Yapay Zeka Katmanı (AI Layer)**  
  - Gemini API entegrasyonu  
  - Bağlamsal hafıza, bulanık eşleştirme, veri çıkarma

UI katmanı, uygulama katmanı ile REST benzeri servisler veya dahili Python servis katmanı aracılığıyla haberleşir; uygulama katmanı da hem SQLite veri tabanına hem de Gemini API’sine bağlanarak iş sürecini tamamlar.

---

### 3. Modül Mimarisi

#### 3.1. WhatsApp Arayüzü Simülasyonu (Streamlit)

**Amaç**: Gerçek WhatsApp Business API’ye bağlanmadan önce, sistemin uçtan uca sipariş yönetim davranışını geliştirmek, test etmek ve demo etmek için bir **simüle mesajlaşma arayüzü** sağlamak.

- **Ana Özellikler**
  - Müşteri rolünde mesaj gönderme (serbest metin giriş alanı).
  - Mesaj geçmişi görünümü (konuşma bazlı zaman çizelgesi).
  - Sipariş özetleri, tahmin edilen ürünler ve toplam tutarların müşteri tarafına yansıtılması.
  - Hata/sorun durumunda (ürün bulunamaması, stok problemi vb.) kullanıcıya açıklayıcı geri bildirim.

- **Veri Akışı**
  1. Kullanıcı, Streamlit arayüzünden serbest metin bir mesaj (örn. “2 adet büyük boy sucuklu pizza ve 1 litre kola”) gönderir.
  2. Uygulama, mesajı **AI Orkestrasyon Servisi**’ne iletir.
  3. AI katmanı Gemini API üzerinden:
     - Mesajdan **müşteri niyetini** ve **ürün/adet bilgilerini** çıkarır,
     - Ürün isimlerini veri tabanındaki ürünlerle **bulanık eşleştirme** ile örtüştürür,
     - Gerekirse önceki mesajları da kullanarak bağlamsal yorum yapar (ör. “aynısından bir tane daha”).
  4. Uygulama katmanı, çıkan ürünleri **Ürünler** tablosuyla doğrular, stok/aktiflik kontrollerini yapar ve bir **geçici sipariş taslağı** oluşturur.
  5. Sipariş taslağı ve özet bilgiler (kalemler, fiyatlar, toplam tutar, tahmini teslim süresi) müşteriye mesaj olarak geri gösterilir.
  6. Müşteri onayı sonrası taslak, **Siparişler** tablosunda kalıcı bir sipariş kaydına dönüştürülür.

Bu simülasyon modülü gelecekte gerçek WhatsApp entegrasyonu ile değiştirilebilir veya paralel olarak çalıştırılabilir. Mimari, I/O arayüzünü soyutlayacak şekilde tasarlanacaktır (örn. `MessageGateway` arayüzü).

#### 3.2. İşletme Sahibi Admin Dashboard’u (Streamlit)

**Amaç**: İşletme sahibine ve operasyon ekibine **anlık görünürlük** ve **kontrol paneli** sağlamak.

- **Ana Özellikler**
  - **Sipariş Listesi**:  
    - Duruma göre filtreleme (Bekleyen, Hazırlanıyor, Teslim Edildi, İptal).  
    - Müşteri, toplam tutar ve zaman damgası görünümü.
  - **Sipariş Detayı**:  
    - Ürün kalemleri, adet, birim fiyat, toplam fiyat.  
    - Sohbet geçmişine hızlı link (ilgili WhatsApp diyaloğuna referans).  
    - Gerekli durumlarda manuel müdahale (sipariş düzenleme, iptal, not ekleme).
  - **Ürün Yönetimi**:  
    - Yeni ürün ekleme, güncelleme, pasife alma.  
    - Fiyat ve stok bilgisi yönetimi (ileride stok yönetimi eklenebilir).
  - **Müşteri Yönetimi**:  
    - Müşteri listesi, iletişim bilgileri, sipariş geçmişi.  
    - VIP/segment etiketlemeleri (ileride kullanılmak üzere).
  - **Raporlama ve KPI’lar** (MVP sonrası):  
    - Günlük/haftalık sipariş sayısı.  
    - Ortalama yanıt süresi.  
    - Manuel müdahale oranı (otonomluk metriği).  
    - Hedeflenen **%50+ manuel iş yükü azaltımı** için izlenen metrikler.

- **Veri Akışı**
  - Dashboard doğrudan SQLite veri tabanına bağlanır (read-heavy).  
  - Sipariş durum güncellemeleri, ürün güncellemeleri gibi **yazma** işlemleri için uygulama katmanı üzerinden gitmesi önerilir (transactional servisler).

---

### 4. Veri Tabanı Katmanı (SQLite)

OrderFlow AI’ın ilk aşamada **tek düğümlü, gömülü ve hafif bir veri tabanı** mimarisi kullanması amacıyla SQLite tercih edilmiştir. Veri tabanı tasarımında **veri bütünlüğü** ve **iş kurallarının tutarlılığı** önceliklidir.

#### 4.1. Genel İlkeler

- **ACID garantisi**: SQLite’ın tek dosyalı yapısından yararlanarak transaction bazlı güncellemelerle tutarlılık sağlanır.
- **Foreign key kısıtları aktif** olacaktır (örn. `PRAGMA foreign_keys = ON`).
- **Normalized şema** (en az 3NF): Müşteri, ürün ve siparişler net şekilde ayrılır.
- **Tüm kritik alanlarda NOT NULL ve uygun veri tipleri** kullanılır.

#### 4.2. Temel Tablolar

- **`customers` (Müşteriler)**
  - `id` (PK, INTEGER, AUTOINCREMENT)
  - `whatsapp_number` (TEXT, UNIQUE, NOT NULL)
  - `name` (TEXT, NULLABLE – her zaman zorunlu olmayabilir)
  - `created_at` (DATETIME, NOT NULL)
  - `updated_at` (DATETIME, NOT NULL)

- **`products` (Ürünler)**
  - `id` (PK, INTEGER, AUTOINCREMENT)
  - `name` (TEXT, NOT NULL, index)
  - `sku` (TEXT, UNIQUE, NULLABLE – MVP’de opsiyonel)
  - `price` (REAL, NOT NULL)
  - `is_active` (BOOLEAN, NOT NULL, default `1`)
  - `created_at` (DATETIME, NOT NULL)
  - `updated_at` (DATETIME, NOT NULL)

- **`orders` (Siparişler)**
  - `id` (PK, INTEGER, AUTOINCREMENT)
  - `customer_id` (INTEGER, FK → `customers.id`, NOT NULL)
  - `status` (TEXT, NOT NULL – `pending`, `confirmed`, `preparing`, `delivered`, `cancelled` gibi enum benzeri değerler)
  - `total_amount` (REAL, NOT NULL)
  - `created_at` (DATETIME, NOT NULL)
  - `updated_at` (DATETIME, NOT NULL)

- **`order_items` (Sipariş Kalemleri)** – veri bütünlüğü için önerilen ek tablo
  - `id` (PK, INTEGER, AUTOINCREMENT)
  - `order_id` (INTEGER, FK → `orders.id`, NOT NULL, ON DELETE CASCADE)
  - `product_id` (INTEGER, FK → `products.id`, NOT NULL)
  - `quantity` (INTEGER, NOT NULL, > 0)
  - `unit_price` (REAL, NOT NULL – sipariş anındaki fiyatı sabitlemek için)
  - `created_at` (DATETIME, NOT NULL)

> Not: Kullanıcı talebinde sadece Müşteriler, Ürünler ve Siparişler belirtilmiş olsa da, **sipariş kalemlerini ayrı tabloda tutmak**, veri bütünlüğü ve esneklik için önerilen standart yaklaşımdır. İstenirse MVP’de sadeleştirilip daha sonra ayrıştırılabilir.

#### 4.3. Veri Bütünlüğü Stratejileri

- **Foreign key kısıtları** ile yetim kayıt engellenir (ör. silinen müşterinin siparişleri için uygun davranış belirlenir).
- **Check kısıtları** (ör. `quantity > 0`, `total_amount >= 0`) ile temel iş kuralları enforce edilir.
- Sipariş oluşturma/iptal operasyonları **transaction** içerisinde yapılır; böylece kısmi yazma hataları engellenir.
- Fiyatlar, sipariş anında `order_items.unit_price` alanına kopyalanarak sonradan ürün fiyatı değişse dahi geçmiş siparişin doğruluğu korunur.

---

### 5. Yapay Zeka Katmanı (Gemini API)

OrderFlow AI, dil anlama ve yapılandırılmamış WhatsApp mesajlarından **yapılandırılmış sipariş verisi çıkarma** için Gemini API’sini kullanacaktır.

#### 5.1. Sorumluluklar

- **Niyet Analizi**  
  - Mesajın sipariş, iptal, adres güncelleme, soru (örn. “menü ne?”) vb. olup olmadığını sınıflandırma.

- **Veri Çıkarma (Information Extraction)**  
  - Ürün adı, adet, varyant (büyük/küçük, sıcak/soğuk), kampanya kodu, teslimat adresi vb. alanların metinden çıkarılması.

- **Bulanık Eşleştirme (Fuzzy Matching)**  
  - Doğal dilde/yanlış yazılmış ürün isimlerinin `products` tablosundaki tanımlarla eşleştirilmesi.  
  - Örn. “sutlaç” → “Sütlaç”, “büyük boy sucuklu pizza” → ilgili SKU.

- **Bağlamsal Hafıza (Contextual Memory)**  
  - Aynı oturum içindeki önceki mesajları kullanarak eksik bilgiyi tamamlamak.  
  - Örn.  
    - Müşteri: “Aynısından bir tane daha.”  
    - Sistem: Son sipariş/son ürün üzerinden adet artırımı veya yeni satır ekleme.

#### 5.2. Entegrasyon Deseni

- **Orkestrasyon Servisi** (ör. `AiOrderOrchestrator`):
  - Girdi: Ham WhatsApp mesajı + oturum kimliği (conversation_id) + opsiyonel müşteri kimliği.
  - İşleyiş:
    1. Gerekli bağlam (önceki mesajlar, mevcut sipariş taslağı, ürün kataloğu özeti) hazırlanır.
    2. Gemini API’ye uyarlanmış, **rol ve örneklerle zenginleştirilmiş prompt** oluşturulur.
    3. Gemini cevabı, iç şema (örn. `ParsedOrderIntent`) formatına parse edilir.
    4. Elde edilen yapılandırılmış veri, uygulama katmanındaki iş kurallarına teslim edilir (stok, fiyat, müşteri doğrulama vb.).
  - Çıktı: Sipariş taslağı, hata/uyarı bilgileri, kullanıcıya gidecek metin cevabı.

- **Güvenlik ve Hata Yönetimi**
  - Tüm Gemini çağrıları için **timeout** ve **retry** mekanizması.
  - Beklenmedik şema hatalarında güvenli degrade (örn. “Mesajınızı tam anlayamadım, lütfen daha net yazar mısınız?”).
  - Günlükleme (logging) ve anonimleştirilmiş prompt/cevap saklama (model iyileştirme için).

---

### 6. Geliştirme Süreci ve Çalışma Pratikleri

#### 6.1. GitHub Flow

Proje, küçük ama sık teslim prensibiyle **GitHub Flow** üzerinden yürütülecektir:

- **`main` branşı**: Her zaman deploy edilebilir, kararlı kodu içerir.
- **Feature branch’ler**:
  - Her yeni özellik veya önemli düzeltme için `feature/<kısa-isim>` formatında ayrı bir branch açılır.
  - Geliştirme bu feature branch üzerinde yapılır.
- **Pull Request (PR) Zorunluluğu**:
  - Tüm değişiklikler PR üzerinden `main`’e taşınır; doğrudan `main`e push yasaktır.
  - Kod gözden geçirme (code review) süreci:
    - Mimari uyum, test kapsamı ve güvenlik etkileri değerlendirilir.
    - Gerekirse Plan Agent üzerinden mimari etki analizi alınır.
- **Sürekli Entegrasyon (CI)** (ilerleyen aşamalar için):
  - Otomatik testler (unit + basit entegrasyon) PR açıldığında tetiklenir.
  - Lint ve format kontrolleri (örn. `ruff`, `black` veya `flake8`).

#### 6.2. AI-Augmented Development Yaklaşımı

OrderFlow AI, geliştirme sürecinde de yapay zekadan yararlanacak şekilde tasarlanmıştır. İki temel ajan rolü tanımlanır:

- **Plan Agent (Mimari Planlama Ajanı)**  
  - Sorumluluklar:
    - Yeni özellikler için **mimari tasarım, modülerleştirme, veri akışları** ve bileşen sınırlarını belirlemek.
    - `ARCHITECTURE.md`, `DESIGN_DECISIONS.md` gibi dokümantasyonların bakımını yapmak.
    - Büyük refaktörler öncesinde etki analizi çıkarmak.
  - Kullanım Zamanı:
    - Yeni modül eklenirken,
    - Özellikle AI katmanı, veri modeli veya entegrasyonlarda mimari karar alınacağı zaman.

- **Skills Agent (Uygulama Geliştirme Ajanı)**  
  - Sorumluluklar:
    - Plan Agent tarafından tanımlanan mimari çerçeve içinde **somut kod üretimi** (Streamlit UI, servis katmanı, DB erişim kodları vb.).
    - Test senaryoları, küçük refaktörler, hata düzeltmeleri.
  - Kullanım Zamanı:
    - Net bir görev tanımı ve kabaca belirlenmiş mimari kararlar mevcutken.

- **Çalışma Prensipleri**
  - Her önemli feature için önce **Plan Agent** devreye alınır, mimari taslak ve görev listesi çıkarılır.
  - Ardından **Skills Agent**, belirlenen görevleri adım adım uygular.
  - Yapılan değişiklikler PR üzerinden gözden geçirilir; gerekirse tekrar Plan Agent’tan mimari güncelleme talep edilir.

Bu yaklaşım, hem insan geliştiriciler hem de AI ajanlar arasında **ortak bir mimari dil** oluşturarak, sistemin uzun vadede yönetilebilir ve genişletilebilir olmasını hedefler.

---

### 7. Yol Haritası (Kısa Özet)

- **Aşama 1 – MVP**
  - WhatsApp simülasyon UI (Streamlit)  
  - Basit Admin Dashboard (sipariş listesi + detay görüntüleme)  
  - SQLite şema kurulumu (Müşteriler, Ürünler, Siparişler, Sipariş Kalemleri)  
  - Gemini ile temel niyet, ürün eşleştirme, karmaşık metinlerden adres ve iletişim bilgilerinin otonom çıkarımı

- **Aşama 2 – Operasyonel Olgunlaşma**
  - Durum bazlı sipariş iş akışları (pending → confirmed → preparing → delivered)  
  - Hata ve edge case senaryolarının kapsanması  
  - Dashboard üzerinden ürün/müşteri yönetiminin tamamlanması  
  - Manuel müdahale gerektiren sipariş oranının ölçümü

- **Aşama 3 – Optimizasyon ve Gerçek Entegrasyonlar**
  - Gerçek WhatsApp Business API entegrasyonu  
  - Gelişmiş raporlama ve KPI takibi  
  - Gelişmiş bağlamsal hafıza stratejileri  
  - Diğer kanal entegrasyonları (örn. web chat, Instagram DM) – opsiyonel

Bu mimari, OrderFlow AI’ın **modüler, ölçeklenebilir ve AI-merkezli** bir sipariş yönetim çözümü olarak evrilmesine imkân verecek şekilde tasarlanmıştır.

