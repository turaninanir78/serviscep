# ServisCep — Teknik Mimari Dokümanı

**Durum:** Faz 0 — planlama (henüz kod, migration veya Docker Compose oluşturulmadı)
**Geliştirici profili:** Tek kişi, Claude Code ile AI-destekli geliştirme, biçimsel yazılım mühendisliği geçmişi yok.

---

## 1. Proje Amacı

ServisCep, işletmelerin müşterilerinden **WhatsApp üzerinden** randevu almasını sağlayan, **çok kiracılı (multi-tenant)** bir SaaS platformudur.

Uzun vadede modüler bir yapı hedefleniyor — klasik (AI'sız) randevu, AI destekli esnek randevu, akıllı bekleme listesi, AI İş Hafızası ve ServisCep hizmet platformu entegrasyonu gibi özellikler zamanla birbirinden bağımsız modüller olarak eklenecek. Bu doküman, bu uzun vadeli hedefe giden yolda **ilk çalışan ürünün (Faz 1) ne olduğunu ve mimarinin buna nasıl hizmet ettiğini** tanımlar.

---

## 2. Faz 1 Kapsamı

İlk çalışan ürün, WhatsApp'a hiç dokunmadan, **API üzerinden uçtan uca test edilebilir bir randevu motoru**dur. Kapsam:

1. Firma / tenant oluşturma
2. Kullanıcı / yönetici oluşturma
3. Personel oluşturma
4. Hizmet oluşturma
5. Çalışma saatlerini belirleme
6. Müşteri oluşturma
7. Boş randevu saatlerini hesaplama
8. Randevu oluşturma
9. Randevu çakışmasını engelleme
10. Randevuları yönetim panelinde gösterme

WhatsApp entegrasyonu **sonraki aşamada**, bu API'ler zaten çalışır ve test edilmiş durumdayken devreye girer. Randevu motorunun doğruluğu WhatsApp'a bağımlı olmadan kanıtlanmalı — sıra önemli: önce motor, sonra kanal.

Faz 1'de aktif olan tek özellik modülü: **`classic_appointments`** (bkz. Bölüm 7).

---

## 3. Faz 1 Dışında Kalan Özellikler

Mimari bunlara **gelecekte** yer açacak şekilde tasarlanıyor, ama Faz 1 implementasyonuna zorunlu olarak eklenmiyor:

- pgvector / embedding altyapısı
- Gerçek AI implementasyonu (niyet ayrıştırma, doğal dil anlama)
- AI İş Hafızası sistemi
- Redis
- RQ / Celery veya başka bir background worker
- Karmaşık subscription / faturalama sistemi
- Gerçek ödeme sistemi entegrasyonu
- Akıllı bekleme listesi implementasyonu
- Meta Embedded Signup otomasyonu
- Fazla karmaşık RLS kuralları

Bunların hiçbiri "yanlış fikir" oldukları için dışarıda değil — Faz 1'in tek işi randevu motorunun doğru çalıştığını kanıtlamak, bu listedekiler henüz doğrulanmamış problemler için erken karmaşıklık olur.

---

## 4. Genel Sistem Mimarisi

Faz 1'de veri akışı WhatsApp'sız, doğrudan API üzerinden:

```
Yönetim Paneli (Next.js)
        ↓
   FastAPI Backend  ←→  PostgreSQL
```

WhatsApp devreye girdiğinde (Faz 1 sonrası) akış şu şekilde genişler, ama **backend'in iş mantığı katmanı değişmez**:

```
WhatsApp mesajı
   → Meta webhook
   → FastAPI (webhook alım noktası)
   → Backend iş mantığı (randevu motoru)
   → PostgreSQL
   → Sonuç
   → n8n (bildirim/otomasyon tetikleme — opsiyonel yan etki)
   → WhatsApp cevabı
```

n8n bu akışta **çekirdek karar noktası değil**, yan etkileri yürüten bir istasyon (bkz. Bölüm 9). Randevu motoru n8n'e bağımlı değildir; n8n tamamen devre dışı bırakılsa bile randevu oluşturma/çakışma kontrolü çalışmaya devam eder.

---

## 5. Teknoloji Seçimi

| Katman | Seçim |
|---|---|
| Frontend | Next.js + TypeScript |
| Backend | Python + FastAPI |
| Veritabanı | PostgreSQL |
| WhatsApp | Meta Cloud API |
| Otomasyon | n8n |
| Local geliştirme | Docker |
| Production | VDS / Cloud |
| AI | Sonradan eklenecek, ayrı modül |

Bu seçimler önceki mimari değerlendirmesinde belirlenmiş ve korunuyor: Next.js Claude Code ile geliştirmede örnek/dokümantasyon yoğunluğu nedeniyle, FastAPI mevcut Python (Solana bot / CEX bot) birikimiyle tutarlılık ve AI fazlarındaki ekosistem olgunluğu nedeniyle tercih edildi. Bu dokümanın odağı teknoloji seçimini yeniden tartışmak değil, Faz 1 kapsamını ve modüler yapıyı netleştirmek.

---

## 6. Multi-Tenant Yaklaşımı

**Temel prensip: her işletme yalnızca kendi verisini görebilir.**

- Tek veritabanı, tek şema, her tabloda `tenant_id` — tenant başına ayrı şema/veritabanı Faz 1'de gereksiz operasyonel yük getirir.
- İzolasyon **öncelikle uygulama katmanında** sağlanır: her sorgu, backend'de "current tenant" bağlamı üzerinden `tenant_id` ile filtrelenir.
- Faz 1'de Postgres RLS politikaları **eklenmiyor** — uygulama katmanındaki tenant scoping'in doğru ve tutarlı çalıştığı test edildikten sonra, ikinci savunma katmanı olarak sonraki fazda değerlendirilecek bir konu. Faz 1'i "hem uygulama hem veritabanı seviyesinde çift kilit" ile başlatmak, henüz tek bir tenant'ın bile üretimde çalışmadığı bir aşamada gereksiz karmaşıklık.

---

## 7. Modüler Özellik / `tenant_features` Yaklaşımı

Sistem uzun vadede modüler olacağı için `tenants` tablosunda tek bir `plan_type` alanı yeterli değil — bir firma birden fazla özelliğe aynı anda sahip olabilmeli.

```
tenant
  ↓
tenant_features
```

Örnek özellik anahtarları (feature flag mantığıyla):

- `classic_appointments`
- `ai_flexible_appointments`
- `smart_waitlist`
- `ai_business_memory`
- `serviscep_integration`

Örnek durum:

```
Firma A: classic_appointments
Firma B: classic_appointments, ai_flexible_appointments
Firma C: ai_business_memory
```

**Faz 1'de tüm tenant'lar için sadece `classic_appointments` aktif olur.** Diğer özellik anahtarları şemada tanımlı olabilir ama hiçbir tenant'a atanmaz ve hiçbir kod yolu bunları kullanmaz. Bu yaklaşımın maliyeti bir tablo + basit bir ilişki; getirisi, ileride "AI paketi olan firmalar" gibi bir ayrım geldiğinde `plan_type` alanını yeniden modellemek yerine sadece yeni bir `tenant_features` satırı eklemek olması.

---

## 8. Randevu Motoru Sorumlulukları

Aşağıdakiler **kesinlikle FastAPI backend içinde** kalır, hiçbir dış sistem (n8n dahil) bu mantığı yönetmez:

- Randevu oluşturma
- Müsaitlik hesaplama (çalışma saatleri − mevcut randevular = boş slotlar)
- Randevu çakışma kontrolü
- Çalışma saatleri yönetimi
- Personel uygunluğu
- Tenant izolasyonu
- Veritabanı işlemleri (transactional bütünlük)

**Klasik randevu mantığı örneği (AI kullanılmadan):**

```
Firma çalışma saatleri: 09:00 - 18:00
Randevu süresi: 60 dakika

Sistem hesaplar: 09:00, 10:00, 11:00, 12:00, ...
```

Bu hesaplama saf iş mantığıdır — framework'ten, WhatsApp'tan ve n8n'den bağımsız, doğrudan test edilebilir bir fonksiyon/servis olarak yazılır. Faz 1'in "bitti" sayılması için ölçüt: bu mantığın WhatsApp hiç devrede olmadan, sadece API çağrılarıyla uçtan uca doğrulanmış olması.

---

## 9. n8n'in Sistemdeki Rolü

**n8n çekirdek uygulama mantığını yönetmez — sadece otomasyon ve entegrasyon katmanıdır.**

n8n'e uygun olanlar (yan etkiler):
- Randevu öncesi hatırlatma mesajı
- No-show sonrası takip mesajı
- Randevu sonrası değerlendirme isteği
- Google Calendar senkronizasyonu gibi ileride eklenecek entegrasyonlar

n8n'e **verilmeyecek** olanlar: Bölüm 8'deki tüm maddeler. Gerekçe: bu işlemler transactional ve tenant-izolasyonu açısından kritik; mantığın bir kısmı n8n workflow'una, bir kısmı backend'e dağılırsa çok kiracılı bir sistemde hata ayıklamak (özellikle solo geliştirici için) orantısız zorlaşır.

Bağlantı yönü: backend, önemli olaylarda (`appointment.created` gibi) n8n'e HTTP ile bilgi verir; n8n bunun üzerine otomasyonu tetikler. Randevu motoru n8n olmadan da tam çalışır durumda olmalı — n8n'in devre dışı kalması (Faz 1'de henüz kurulmamış olması dahil) randevu oluşturmayı etkilememeli.

Faz 1'de WhatsApp henüz devrede olmadığı için **n8n'in Faz 1'de fiilen bir işlevi yok** — kurulumu ve entegrasyonu WhatsApp aşamasıyla birlikte gelir.

---

## 10. WhatsApp Entegrasyon Mimarisi

**Faz 1'de implement edilmiyor** — bu bölüm, veri modelinin ve mimarinin gelecekte bunu desteklemeye hazır olması için tutuluyor.

- Bir tenant'ın WhatsApp hesabı **olabilir** (zorunlu değil — Faz 1'de hiçbir tenant'ın WhatsApp bağlantısı yok).
- `phone_number_id` saklanabilecek şekilde şemada yer ayrılır.
- WhatsApp Business Account (WABA) bağlantısı ileride desteklenir.
- İlk prototipte (WhatsApp devreye girdiğinde) bağlantı **manuel** kurulur — her tenant kendi Meta hesabını kurar, `phone_number_id` ve erişim bilgilerini panelden girer.
- **Meta Embedded Signup şu anda implement edilmiyor** — tenant sayısı arttığında ayrı bir iş kalemi olarak ele alınacak.
- Access token ve benzeri hassas bilgiler, açık metin olarak değil, güvenli saklama prensibine uygun şekilde tasarlanacak (şifreleme yöntemi implementasyon aşamasında netleşir — Faz 1'de karar verilmesi gerekmiyor, çünkü henüz hiçbir token saklanmıyor).

---

## 11. Gelecekte AI Entegrasyonu

AI, ayrı bir modül olarak (`ai_flexible_appointments` özellik anahtarı üzerinden, bkz. Bölüm 7) ileride eklenecek. Örnek akış:

```
Müşteri: "Yarın öğleden sonra gelebilir miyim?"
AI: tarihi ve zaman aralığını anlar
    → backend randevu motoruna (Bölüm 8) sorgu gönderir
    → uygun seçenekleri müşteriye sunar
```

Kritik nokta: AI, randevu motorunun **üzerine** konumlanan bir katmandır — kendi çakışma kontrolü veya müsaitlik hesabı yapmaz, mevcut backend API'lerini çağırır. Bu sayede AI modülü eklendiğinde randevu motorunun kendisi değişmez, sadece yeni bir giriş noktası (doğal dil → API çağrısı) eklenmiş olur.

**Faz 1'de AI kodu yazılmıyor.** Bu bölümün tek amacı, ileride bu modülün eklenmesinin randevu motorunda bir yeniden yazım gerektirmeyeceğini mimari olarak garanti altına almak.

---

## 12. Database Genel Yapısı

Faz 1 için değerlendirilen temel tablolar:

```
tenants
users              -- işletme paneline giriş yapan kişiler
tenant_features    -- tenant ↔ özellik anahtarı ilişkisi (Bölüm 7)
customers          -- işletmenin kendi müşterileri
staff_members
services
availability_rules -- çalışma saatleri
appointments
```

Aşağıdaki tablolar Faz 1'e dahil edilmiyor, sonraki fazlara bırakılıyor:

- `conversations` / `messages` (WhatsApp mesaj geçmişi — WhatsApp entegrasyonuyla birlikte gelir)
- `waitlist` (akıllı bekleme listesi)
- `business_memory_notes` / `ai_memory`
- `subscriptions` (gerçek faturalama sistemiyle birlikte gelir)

Multi-tenant izolasyonu (Bölüm 6) tüm tablolarda temel prensip, ama Faz 1'de bu sadece `tenant_id` kolonu + uygulama katmanı filtresi olarak uygulanıyor — RLS gibi ek katmanlar eklenmiyor.

---

## 13. API Sınırları

Backend, Faz 1'de iki tür tüketiciye hizmet verir:

- **Yönetim paneli (Next.js):** Firma/kullanıcı/personel/hizmet/çalışma saati yönetimi, randevu oluşturma/görüntüleme — kimlik doğrulamalı (giriş yapmış kullanıcı).
- **Doğrudan API testleri:** Faz 1'in doğrulanma yöntemi budur — WhatsApp veya panel olmadan, API çağrılarıyla randevu motorunun uçtan uca doğru çalıştığı gösterilir.

WhatsApp webhook endpoint'i bu fazda **yok** — Bölüm 10'da tarif edilen entegrasyon geldiğinde ayrı bir giriş noktası olarak eklenecek, mevcut API'leri değiştirmeyecek.

Backend içi klasörleme sınırı netleştirilir:

```
backend/
├── app/
│   ├── api/        -- HTTP route'lar (panel API'si; Faz 1'de WhatsApp yok)
│   ├── core/        -- çakışma kontrolü, müsaitlik hesabı, tenant scoping (saf iş mantığı)
│   ├── models/      -- veritabanı modelleri
│   ├── schemas/      -- request/response şemaları
│   ├── services/     -- iş mantığı orkestrasyonu (api katmanı ile core arasında)
│   └── main.py
├── tests/
└── requirements.txt veya pyproject.toml
```

`core/` katmanının framework'ten (FastAPI'den) bağımsız, saf Python fonksiyonları olarak yazılması — bu, Bölüm 8'deki "randevu motoru API'den, panelden, ileride WhatsApp'tan ve AI'dan aynı şekilde çağrılabilmeli" gerekliliğinin doğrudan karşılığı.

---

## 14. Frontend Sorumlulukları

Next.js uygulaması Faz 1'de sadece **yönetim paneli**dir:

- Firma/tenant bilgisi ve ayarları
- Kullanıcı/personel yönetimi
- Hizmet tanımlama
- Çalışma saatleri girişi
- Müşteri listesi
- Randevu takvimi (görüntüleme + oluşturma)

Frontend'de **iş mantığı çalışmaz** — çakışma kontrolü, müsaitlik hesabı gibi işlemler backend API'sinden gelen sonuçları gösterir, kendi başına hesaplama yapmaz. Bu ayrım, ileride WhatsApp veya AI gibi başka bir "istemci" eklendiğinde panelin özel bir konumu olmamasını sağlar — hepsi aynı backend API'sini kullanır.

Faz 1'de müşteri tarafında ayrı bir arayüz yoktur.

---

## 15. Local Docker Geliştirme Ortamı

Faz 1'de Docker Compose dosyası **henüz oluşturulmuyor** (bu doküman kapsamı sadece mimari kararlar). İleride kurulacağında minimum servis seti:

```
postgres
backend   (FastAPI)
frontend  (Next.js)
```

n8n, Faz 1'de fiilen kullanılmadığı için (Bölüm 9) local ortamda zorunlu değil; WhatsApp entegrasyonu başladığında eklenir. Redis ve benzeri kuyruk altyapısı da aynı şekilde, gerçek bir ihtiyaç (webhook arkası asenkron işlem) doğduğunda eklenir — Faz 1'de sentetik olarak eklenmez.

---

## 16. Production / VDS Geçiş Planı

Faz 1'in production'a taşınması, önceki genel mimari değerlendirmesinde belirlenen prensiple uyumlu: yerel ortamda çalışan Docker Compose seti, VDS'te aynen çalışır; ortam farkı sadece `.env` içeriğinde olur.

Faz 1 kapsamında production'a taşıma henüz gündemde değil — önce randevu motorunun yerel ortamda API üzerinden doğrulanması gerekiyor. VDS/hosting sağlayıcı seçimi ve geçiş adımları, Faz 1 tamamlanıp WhatsApp entegrasyonuna geçilirken tekrar ele alınacak bir konu.

---

## 17. Güvenlik Prensipleri

Faz 1 kapsamında öncelik sırası:

1. **Tenant izolasyonu** — her API çağrısında, giriş yapmış kullanıcının `tenant_id`'si dışındaki verilere erişim mümkün olmamalı. Bu, Faz 1'in en kritik güvenlik gereksinimi (Bölüm 6).
2. **Kimlik doğrulama** — panel girişi için standart, kendi barındırılan bir auth mekanizması (şifre hash'leme + oturum/token yönetimi); üçüncü parti bir servise bağımlılık Faz 1'de gerekmiyor.
3. **Hassas veri saklama prensibi** — Faz 1'de WhatsApp access token gibi hassas veriler henüz sisteme girmiyor, ama şema tasarımı ileride bunları güvenli saklayacak şekilde (Bölüm 10) planlanmalı; bu, "şimdiden şifreleme altyapısı kurmak" değil, "ileride kurmayı zorlaştıracak bir tasarım hatası yapmamak" anlamına geliyor.

RLS gibi veritabanı seviyesi ek güvenlik katmanları, Bölüm 6'da belirtildiği gibi Faz 1'de bilinçli olarak dışarıda bırakılıyor.

---

## 18. Uygulama Geliştirme Fazları

**Faz 1 — Randevu Motoru (bu doküman kapsamı):**
Bölüm 2'deki 10 maddenin tamamı, WhatsApp olmadan, API üzerinden uçtan uca çalışır ve test edilebilir durumda.

**Faz 1.5 — WhatsApp Bağlantısı:**
Faz 1'de doğrulanmış randevu motoru, Bölüm 10'da tarif edilen manuel WhatsApp bağlantısı üzerinden dış dünyaya açılır. n8n bu aşamada devreye girer (Bölüm 9).

**Faz 2 — Modüler Genişleme:**
`tenant_features` yapısı (Bölüm 7) üzerinden yeni özellikler tek tek eklenir: AI destekli esnek randevu (Bölüm 11), akıllı bekleme listesi, AI İş Hafızası. Her biri ayrı bir özellik anahtarı olarak, mevcut `classic_appointments` mantığını bozmadan eklenir.

**Faz 3 — Platform Entegrasyonu:**
ServisCep hizmet platformu entegrasyonu (`serviscep_integration`).

---

*Bu doküman Faz 1 öncesi karar kaydı olarak tutulmalı. Kapsam veya teknoloji kararı değiştirilirse, bu dosyaya değişiklik + gerekçe eklenmeli, sessizce değiştirilmemeli.*
