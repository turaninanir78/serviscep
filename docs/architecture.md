# ServisCep — Teknik Mimari Önerisi

**Durum:** Taslak / Faz 0 (henüz kod yazılmadı)
**Kapsam:** WhatsApp üzerinden randevu alan çok kiracılı (multi-tenant) SaaS
**Geliştirici profili:** Tek kişi, Claude Code ile AI-destekli geliştirme, biçimsel yazılım mühendisliği geçmişi yok, VDS/cloud hedefi henüz seçilmedi.

---

## 0. Tasarım İlkeleri

Bu mimari üç kısıtı öncelikli tutuyor:

1. **Solo + AI-assisted geliştirmeye uygunluk** — Claude Code'un bol örnek/dokümantasyona sahip olduğu, "sıradan" (boring/mainstream) teknolojiler tercih edildi. Egzotik veya az bilinen framework'ler, AI-assisted geliştirmede hata oranını artırır.
2. **Faz 1'i şişirmeden Faz 2+'ya kapı bırakmak** — AI İş Hafızası, akıllı bekleme listesi ve platform entegrasyonu gibi ileri özellikler için veri modeli ve servis katmanları şimdiden esnek bırakılıyor, ama bu özellikler Faz 1'de **inşa edilmiyor**.
3. **Yerelde çalışan her şeyin VDS'te aynen çalışması** — Docker Compose tabanlı, ortam farkı sadece `.env` ve domain/TLS ayarında olacak şekilde.

Aşağıdaki her başlıkta seçim + gerekçe + reddedilen alternatif birlikte veriliyor.

---

## 1. Frontend

**Seçim: Next.js (TypeScript) + Tailwind CSS + shadcn/ui**

- İşletme paneli (randevu takvimi, hizmet/personel yönetimi, WhatsApp bağlantı durumu) klasik bir CRUD-ağırlıklı admin dashboard'u — shadcn/ui'nin hazır tablo/form/takvim bileşenleri bu işi hızlandırır.
- Next.js hem pazarlama sitesini (serviscep.com) hem işletme panelini (app.serviscep.com) tek repo/tek deploy biriminde barındırabilir — solo geliştirmede ayrı repo yönetiminin getirdiği ek yük ortadan kalkar.
- Claude Code'un Next.js/React ekosistemine dair eğitim verisi yoğunluğu, framework hatası riskini düşürür — bu senin mevcut Solana bot / CEX bot deneyimindeki Python tercihine paralel bir "az sürprizli teknoloji" mantığı.
- Vercel'e bağımlı değil: `next build` çıktısı Docker container içinde `node server.js` ile VDS'te de sorunsuz çalışır (bkz. Bölüm 6).

**Reddedilen alternatif:** SvelteKit — daha hafif ve performanslı olsa da, Claude Code için örnek yoğunluğu ve ekosistem desteği Next.js kadar güçlü değil; solo/AI-assisted geliştirmede bu risk performans kazancına değmiyor.

**Not:** Faz 1'de müşteri tarafında ayrı bir web arayüzü **yok** — müşteri deneyimi tamamen WhatsApp içinde. İleride "linkle randevu al" gibi bir fallback gerekirse aynı Next.js app içinde `/book/[tenant]` route'u olarak eklenir, ayrı bir proje gerekmez.

---

## 2. Backend

**Seçim: Python + FastAPI**

Gerekçe, framework kalitesinden çok **senin mevcut bağlamınla tutarlılık** üzerinden:

- Solana bot ve CEX bot'ta zaten Python'da derin pratik birikimin var (async iş, servis katmanları, scoring/karar mantığı ayrıştırma) — aynı dili kullanmak, Claude Code ile üretilen kodu okuyup denetleme kapasiteni doğrudan artırır.
- ChainLens için zaten planladığın "FastAPI backend → JSON endpoint" deseniyle bu proje aynı iskelete oturuyor; ileride iki proje arasında kod/](ör. Stage-1 tarzı filtre mantığı, AI karar-katmanı desenleri) paylaşımı mümkün olur.
- AI İş Hafızası (Bölüm 9) ve AI-destekli esnek randevu paketi geldiğinde ihtiyaç duyacağın embedding/LLM orkestrasyon kütüphanelerinin (LangChain, LlamaIndex, doğrudan Anthropic/OpenAI SDK'ları) en olgun ekosistemi Python'da.
- FastAPI'nin native `async def` desteği, WhatsApp webhook'unun Meta'nın kısa timeout penceresine hızlı yanıt verip işlemi arkaya devretmesi için doğrudan uygun (Bölüm 8).

**Reddedilen alternatif:** Node.js/NestJS — frontend ile aynı dil olması (TypeScript full-stack) cazip, ama (a) senin var olan Python birikimini kullanmıyor, (b) gelecekteki AI-ağırlıklı fazlarda ekosistem avantajı FastAPI'de. Tek-dil rahatlığı, bu projede ikinci öncelik.

**İç yapı (Faz 1 iskeleti, kod değil — sadece katmanlama fikri):**
- `api/` — HTTP route'lar (dashboard REST API + WhatsApp webhook)
- `core/` — randevu çakışma kontrolü, çalışma saati mantığı, tenant scoping (saf iş mantığı, framework'ten bağımsız)
- `integrations/` — WhatsApp Cloud API client, n8n webhook çağrıları
- `ai/` — Faz 1'de kural-tabanlı basit niyet ayrıştırma; Faz 2'de AI İş Hafızası bu klasöre girer (bkz. Bölüm 9 — bu ayrım CEX bot'taki mekanik/AI karar katmanı ayrımıyla birebir aynı desen)

---

## 3. PostgreSQL Veri Modeli

Ana tablolar (Faz 1 kapsamı, isimler taslak):

```
tenants
  id, name, whatsapp_phone_number_id (unique), whatsapp_waba_id,
  plan_type (classic|ai_flex), timezone, created_at

users                -- işletme paneline giriş yapan kişiler
  id, tenant_id, email, password_hash, role (owner|staff), created_at

customers             -- işletmenin kendi müşterileri (WhatsApp üzerinden gelen)
  id, tenant_id, whatsapp_number, display_name, first_seen_at

services               -- işletmenin sunduğu hizmet tipleri
  id, tenant_id, name, duration_minutes, price, is_active

staff_members          -- randevuyu fiilen veren kişi (owner ile aynı olabilir)
  id, tenant_id, name, is_active

availability_rules     -- çalışma saatleri / müsaitlik
  id, tenant_id, staff_id, weekday, start_time, end_time

appointments
  id, tenant_id, customer_id, service_id, staff_id,
  start_at, end_at, status (pending|confirmed|cancelled|completed|no_show),
  created_via (whatsapp|dashboard), created_at

conversations           -- WhatsApp mesaj geçmişi (ham log)
  id, tenant_id, customer_id, direction (in|out), message_text,
  wa_message_id, created_at

waitlist_entries        -- Faz 2: akıllı bekleme listesi (şimdiden şemada yer ayır)
  id, tenant_id, customer_id, desired_service_id, desired_window_start,
  desired_window_end, status

business_memory_notes   -- Faz 2: AI İş Hafızası (şimdiden şemada yer ayır)
  id, tenant_id, customer_id (nullable), content, embedding (vector), created_at

subscriptions
  id, tenant_id, plan_type, status, started_at, renewed_at
```

**Neden `conversations` Faz 1'den itibaren var:** AI İş Hafızası'nın "hammaddesi" geçmiş WhatsApp yazışmalarıdır. Bunu Faz 1'de loglamazsan, Faz 2'ye geçtiğinde geriye dönük veri kaybetmiş olursun — bu tablo maliyeti neredeyse sıfır, sonradan eklenmesi ise veri kaybı demek.

**pgvector uzantısı:** Faz 1'de kullanılmasa bile Postgres imajına `pgvector` eklenmesi öneriliyor (bkz. Bölüm 6, Docker imajı). Uzantıyı sonradan eklemek kolay ama migration sürprizlerini şimdiden ortadan kaldırmak neredeyse maliyetsiz.

---

## 4. Multi-Tenant Mimari

**Seçim: Tek veritabanı, tek şema, her tabloda `tenant_id` + Postgres Row-Level Security (RLS)**

- **Schema-per-tenant** veya **database-per-tenant** modelleri, tenant sayısı arttıkça migration/backup/monitoring karmaşıklığını katlayarak büyütür — solo bir geliştirici için bu, ölçeklenmeden önce operasyonel yük olarak ölçeklenir. ServisCep'in beklenen tenant sayısı (onlarca–yüzlerce işletme, milyonlarca değil) paylaşımlı şema modelini fazlasıyla destekler.
- **Uygulama katmanında tenant scoping birincil savunma:** Her sorgu ORM/query katmanında `tenant_id` filtresiyle geçer (ör. FastAPI dependency injection ile "current_tenant" context'i her request'e enjekte edilir).
- **Postgres RLS ikincil savunma hattı olarak aktif edilir:** Uygulama kodunda bir yerde tenant filtresi unutulsa bile veritabanı seviyesinde çapraz-tenant veri sızıntısını engeller. Solo geliştirmede insan hatası riski daha yüksek olduğundan bu ikinci katman önemli.

**Tenant çözümleme (tenant resolution) iki farklı kanaldan gelir:**
1. **Dashboard girişi:** Kullanıcı login olur → `users.tenant_id` üzerinden otomatik belirlenir. Faz 1'de subdomain (`isletme.serviscep.com`) gerekmez, gereksiz karmaşıklık; login + tek tenant context yeterli.
2. **WhatsApp webhook'u:** Gelen mesajın Meta payload'ındaki `phone_number_id` alanı, `tenants.whatsapp_phone_number_id` ile eşleştirilerek tenant bulunur (bkz. Bölüm 8).

---

## 5. Authentication

**Seçim: Kendi barındırdığın JWT tabanlı auth (FastAPI + `passlib` + access/refresh token, refresh token httpOnly cookie'de)**

- Auth0/Clerk gibi yönetilen servisler hız kazandırır ama (a) aylık maliyet ekler, (b) VDS'e tam geçiş hedefiyle kısmen çelişir — kullanıcı kimlik verisi üçüncü parti servise bağımlı kalır. Erken aşama bir SaaS için bu bağımlılığı şimdiden almak gerekmiyor.
- Kapsam sınırlı: sadece işletme paneli girişi (email+şifre) ve rol bazlı yetkilendirme (owner/staff, ileride ServisCep iç ekibi için super-admin). Bu kapsamda özel auth yazmak, Claude Code ile birkaç saatlik iş — dışarıdan servise ihtiyaç doğuracak kadar karmaşık değil.
- Müşteri (WhatsApp kullanıcısı) için ayrı bir auth **yok** — kimlik doğrulama WhatsApp numarası üzerinden zaten doğal olarak sağlanıyor.

**Reddedilen alternatif:** Supabase (Auth + Postgres + Storage hepsi bir arada) — cazip bir hızlandırıcı, ama VDS'e geçiş planınla (Bölüm 10) gerilir; Supabase'in yönetilen Postgres'i kendi VDS'indeki Postgres ile aynı şey değil, ileride migration gerektirir. Şimdiden kendi Postgres'ini kendin işletmek, uzun vadede tekrar taşınma riskini ortadan kaldırıyor.

---

## 6. Docker Yapısı

Tek `docker-compose.yml`, hem yerelde hem VDS'te aynı:

```
services:
  postgres      # pgvector/pgvector:pg16 imajı (pgvector şimdiden hazır)
  backend       # FastAPI + uvicorn
  frontend      # Next.js (production build, node server)
  n8n           # resmi n8nio/n8n imajı
  redis         # webhook arkası kuyruk + basit cache + rate limit
  caddy         # reverse proxy + otomatik TLS (Let's Encrypt)
```

- **Redis'in eklenme gerekçesi:** WhatsApp webhook'u Meta'ya hızlı 200 OK dönmeli; asıl işlem (niyet ayrıştırma, DB yazımı, n8n tetikleme) arka planda kuyruğa alınmalı. FastAPI `BackgroundTasks` Faz 1 için yeterli olabilir, ama Redis + basit bir worker (RQ) şimdiden compose'da bulunması, mesaj hacmi arttığında kod değişikliği değil sadece worker sayısı artırma sorunu haline getirir.
- **Caddy tercih edildi (Nginx yerine):** Otomatik Let's Encrypt sertifika yenilemesi tek satır config ile geliyor — solo geliştiricinin manuel certbot cron'u yönetmesine gerek kalmıyor.
- **Yerel/VDS farkı sadece `.env`'de:** `DATABASE_URL`, `WHATSAPP_ACCESS_TOKEN`, `DOMAIN` gibi değişkenler değişir; compose dosyasının kendisi değişmez. Bu, "yerelde çalışıyor ama sunucuda çalışmıyor" sınıfı sorunları yapısal olarak engeller.

---

## 7. n8n Entegrasyonu

**Rolü net sınırlandırılmalı: n8n çekirdek randevu mantığını içermez, sadece yan-etki otomasyonlarını yürütür.**

- **Backend'de kalması gereken (n8n'e devredilmeyecek):** Randevu çakışma kontrolü, müsaitlik hesaplama, tenant-scoping, veri bütünlüğü — bunlar transactional ve tenant-izolasyonu kritik işlemler; n8n workflow'u içinde dağınık iş mantığı, çoklu tenant'ta hata ayıklamayı (debugging) çok zorlaştırır.
- **n8n'e uygun olanlar:** Randevu öncesi hatırlatma mesajı gönderme, no-show sonrası takip mesajı, randevu sonrası değerlendirme isteği, Google Calendar senkronizasyonu, plan bazlı otomasyon kuralları (ör. AI paketindeki ekstra bildirimler).
- **Bağlantı yönü:** Backend, önemli olaylarda (`appointment.created`, `appointment.completed` vb.) n8n'in webhook node'una HTTP POST atar. n8n, gerektiğinde backend'in iç API'sine geri çağrı yapabilir (ör. "bu müşteriye özel not var mı?"). WhatsApp mesajlarının **birincil alım noktası backend'dir**, n8n değil — çünkü webhook güvenilirliği ve DB yazım garantisi backend'de daha kolay denetlenir.

---

## 8. WhatsApp Meta Cloud API Entegrasyonu

Bu bölüm en kritik mimari karar noktası, çünkü multi-tenant + WhatsApp kombinasyonu tek numaralı bir bot'tan farklı kurallar getiriyor.

**Model: Her tenant'ın kendi WhatsApp Business numarası olur (paylaşımlı tek numara değil).**

Gerekçe: "İşletmelerin müşterilerinden randevu alması" senaryosunda müşteri, kendi gittiği işletmenin WhatsApp'ına yazıyor olmalı — paylaşımlı tek bir ServisCep numarası, her işletme için markasızlaşma ve müşteri kafa karışıklığı yaratır.

**Faz 1 onboarding (manuel, otomatikleştirilmemiş):**
- Her yeni tenant, kendi Meta Business Manager + WhatsApp Business Account (WABA) hesabını kurar, telefon numarasını Cloud API'ye bağlar, `phone_number_id` ve access token'ı ServisCep'e (dashboard üzerinden) girer.
- Bu süreç ilk birkaç pilot müşteri için elle yürütülebilir; otomasyon (Embedded Signup + Meta Tech Provider/Solution Partner statüsü) ciddi bir onboarding sürtünmesi problemi haline geldiğinde (tenant sayısı arttıkça) ayrı bir iş kalemi olarak ele alınmalı. Faz 1'de bunu inşa etmek, henüz doğrulanmamış bir problem için erken optimizasyon olur.

**Webhook mimarisi:**
- Meta, uygulama başına **tek** webhook URL'i kabul eder (tenant başına değil) — bu yüzden tüm tenant'ların mesajları aynı `/webhooks/whatsapp` endpoint'ine düşer.
- Gelen her payload'daki `phone_number_id` alanı, `tenants.whatsapp_phone_number_id` ile eşleştirilerek doğru tenant bulunur (bkz. Bölüm 4).
- Endpoint, Meta'nın kısa timeout'u nedeniyle **hemen 200 OK döner**, gerçek işleme (niyet ayrıştırma, DB yazımı, n8n tetikleme) Redis kuyruğuna devredilir (bkz. Bölüm 6).

---

## 9. AI İş Hafızası — Gelecekte Eklenebilirlik

Faz 1'de **inşa edilmiyor**, ama şu üç tasarım kararı şimdiden alınırsa Faz 2'de şema/mimari değişikliği gerekmez:

1. **`conversations` tablosu Faz 1'den itibaren tüm WhatsApp yazışmalarını ham metin olarak saklar** (Bölüm 3) — AI İş Hafızası'nın eğitim/bağlam verisi budur; sonradan eklenirse geçmiş veri kaybolur.
2. **`pgvector` uzantısı Postgres imajında Faz 1'den itibaren hazır** (Bölüm 3, 6) — kullanılmasa bile varlığı, ileride embedding tablosu eklerken migration riski taşımaz.
3. **`ai/` katmanı (Bölüm 2) Faz 1'de basit kural-tabanlı niyet ayrıştırma yapar, ama arayüzü ("bu mesaj bir randevu talebi mi", "hangi hizmet isteniyor") sabit tutulur.** Faz 2'de bu arayüzün arkasına AI İş Hafızası destekli daha akıllı bir implementasyon konur; webhook katmanı veya veri modeli değişmez. Bu, CEX bot'ta mekanik skor ile AI karar katmanını ayırdığın desenle birebir aynı mantık — ve orada işe yaradığı zaten kanıtlandı.

---

## 10. Yerel Geliştirmeden VDS/Cloud'a Geçiş

**VDS önerisi: Hetzner Cloud, Avrupa lokasyonu (Almanya/Finlandiya), CX-serisi**

Gerekçe:
- Fiyat/performans oranı bootstrapped solo SaaS için GCP/AWS'e göre belirgin şekilde daha iyi — CEX bot'taki GCP VM deneyimin bir trading bot için mantıklıydı (tek kullanıcı, tek amaç), ama burada müşteri verisi barındıran çok kiracılı bir SaaS için maliyet ölçeklenebilirliği daha kritik.
- Avrupa lokasyonu, Türkiye pazarına yönelik bir üründe müşteri verisinin (randevu, telefon numarası, yazışma) KVKK'ya benzer AB veri koruma standartlarına tabi bir bölgede durması açısından ek bir güven unsuru — bu bir zorunluluk değil ama düşük maliyetli bir artı.
- GCP, mevcut deneyimin nedeniyle bir yedek seçenek olarak akılda tutulabilir, ama bu proje için ilk tercih değil.

**Geçiş mekanizması:**
- Yerel geliştirme ortamı = `docker-compose.yml` (Bölüm 6) ile birebir aynı servis seti.
- VDS'e ilk kurulum: Docker + Docker Compose kurulumu, repo `git clone`, `.env.production` doldurulması, `docker compose up -d --build`.
- Kod güncellemesi iş akışı (senin scp/ssh alışkanlığınla uyumlu, ekstra CI/CD karmaşıklığı olmadan): VDS'e SSH → `git pull` → `docker compose up -d --build`. GitHub Actions tabanlı otomatik deploy, tenant sayısı ve deploy sıklığı arttığında değerlendirilecek bir sonraki adım — Faz 1'de gereksiz karmaşıklık.
- **Yedekleme (Faz 1'den itibaren zorunlu, trading bot'tan farklı olarak burada gerçek müşteri verisi var):** Günlük `pg_dump` cron job'u, Backblaze B2 veya S3-uyumlu bir depoya offsite yedek. Bu, CEX bot'ta olmayan ama SaaS için gözden kaçırılmaması gereken bir kalemdir.
- **VM reboot sonrası otomatik ayağa kalkma:** CEX bot'ta sonradan fark edilip kapatılan bir boşluktu (systemd service eklenerek çözüldü) — burada `docker compose` servisleri `restart: always` politikasıyla tanımlanarak bu sorun Faz 1'den itibaren baştan kapatılıyor.

---

## Özet Tablo

| Katman | Seçim | Ana Gerekçe |
|---|---|---|
| Frontend | Next.js + TS + shadcn/ui | Claude Code uyumu, tek repo (site+panel) |
| Backend | Python + FastAPI | Mevcut Python birikimi, AI ekosistemi |
| Veritabanı | PostgreSQL + pgvector | RLS ile güvenli multi-tenant, AI'ya hazır |
| Multi-tenant | Paylaşımlı şema + `tenant_id` + RLS | Solo geliştirmede operasyonel sadelik |
| Auth | Kendi JWT (FastAPI) | Vendor bağımlılığı yok, VDS uyumlu |
| Konteynerizasyon | Docker Compose (+Redis, Caddy) | Yerel=prod, otomatik TLS |
| Otomasyon | n8n (yan-etkiler için) | Çekirdek mantık backend'de kalır |
| WhatsApp | Tenant başına ayrı numara, tek webhook | Marka bütünlüğü + Meta kısıtı |
| Hosting | Hetzner Cloud (AB) | Maliyet + veri lokasyonu |

---

*Bu doküman Faz 1 öncesi karar kaydı olarak tutulmalı. Herhangi bir teknoloji seçimi değiştirilirse, bu dosyaya değişiklik + gerekçe eklenmeli (sessizce değiştirilmemeli).*
