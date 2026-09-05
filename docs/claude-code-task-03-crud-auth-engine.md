# Claude Code Görevi 03 — CRUD API + Auth + Randevu Motoru

## Bağlam

`docs/architecture.md` referans. Bölüm 2 (Faz 1 kapsamı), Bölüm 8 (randevu motoru sorumlulukları), Bölüm 13 (API sınırları) ve Bölüm 17 (güvenlik) bu görevin doğrudan kaynağı.

Veri modeli (0001 + 0002 migration'ları) zaten hazır ve tenant-izolasyonu DB seviyesinde composite FK ile garanti altında. Bu görevde o şemanın üzerine API katmanı ve çekirdek iş mantığı inşa ediliyor.

**Bu görev Faz 1'in son parçası.** Bitince WhatsApp'a hiç dokunmadan, sadece API çağrılarıyla uçtan uca bir randevu oluşturulup çakışma kontrolünden geçebiliyor olmalı.

## Yapılacaklar

### 1. Auth

- `POST /auth/register` — yeni bir tenant + o tenant'ın ilk kullanıcısını (role=owner) tek işlemde oluşturur. Auth gerektirmez (herkese açık — yeni firma kaydı).
- `POST /auth/login` — email+şifre ile giriş, access token (JWT) döner. Token içinde `user_id` ve `tenant_id` claim olarak bulunmalı.
- Şifreler `passlib` ile hash'lenmeli, düz metin asla saklanmamalı.
- Refresh token mekanizması bu aşamada **gerekmiyor** — tek access token yeterli (kısa/orta ömürlü, ör. 24 saat). Refresh token rotasyonu ayrı bir task'e bırakılıyor.
- Rol ayrımı (owner/staff) DB'de zaten var ama bu görevde **ince yetki kontrolü yapılmayacak** — sadece "geçerli token var mı, hangi tenant'a ait" kontrolü yeterli. "Sadece owner şunu yapabilir" gibi kurallar ayrı bir task.

### 2. Tenant Scoping (kritik)

- Tüm korumalı endpoint'ler, JWT'den çözülen `tenant_id`'yi bir FastAPI dependency (`get_current_tenant` gibi) üzerinden alır.
- Her sorgu bu `tenant_id` ile otomatik filtrelenir — endpoint kodunda `tenant_id` unutulması riskini azaltmak için bu dependency'nin tüm route'larda zorunlu kullanılması gerekiyor, tek tek endpoint içinde elle filtre yazılmamalı (ortak bir query-scoping yardımcı fonksiyonu/base repository düşünülebilir).

### 3. CRUD Endpoint'leri (hepsi auth korumalı, kendi tenant'ıyla sınırlı)

- `staff_members`: create, list, get, update
- `services`: create, list, get, update
- `availability_rules`: create, list, update
- `customers`: create, list, get
- `appointments`: create, list, get (detay Bölüm 4'te)

Silme (`DELETE`) bu görevde **gerekmiyor** — Faz 1'de kayıtları pasifleştirme (`is_active=false`) yeterli, zaten `services.is_active` ve `staff_members.is_active` şemada var.

### 4. Randevu Motoru (`app/core/` katmanı — framework'ten bağımsız, saf fonksiyonlar)

İki temel fonksiyon, FastAPI'den, DB session'dan mümkün olduğunca izole, birim testlerle doğrulanabilir şekilde yazılmalı:

**a) Müsaitlik hesabı:**
```
compute_available_slots(
    availability_rules: list,
    existing_appointments: list,
    service_duration_minutes: int,
    target_date: date,
) -> list[time]
```
Çalışma saatleri içinde, mevcut randevularla çakışmayan, hizmet süresine göre bölünmüş boş slotları döner.

**b) Çakışma kontrolü:**
```
has_conflict(
    existing_appointments: list,
    new_start: datetime,
    new_end: datetime,
    staff_id: int,
) -> bool
```
Aynı personelin aynı zaman aralığında başka bir randevusu var mı kontrol eder.

Bu iki fonksiyon için **birim testleri yazılmalı** (`tests/` klasöründe) — en az: tam dolu gün (boş slot yok), kısmi dolu gün, çakışan randevu reddi, çakışmayan randevu kabulü senaryoları.

### 5. Randevu Oluşturma Endpoint'i

- `GET /availability/slots?staff_id=&service_id=&date=` — o gün için boş slotları döner (yukarıdaki `compute_available_slots` çağrılır).
- `POST /appointments` — randevu oluşturur; önce `has_conflict` ile kontrol eder, çakışma varsa `409 Conflict` döner, yoksa DB'ye yazar.
- Bu iki endpoint, `core/` katmanındaki fonksiyonları çağırır — çakışma/müsaitlik mantığının kendisi endpoint kodunun içine yazılmamalı.

## Yapılmayacaklar (kapsam dışı)

- WhatsApp, n8n, AI — hiçbiri
- Refresh token, "şifremi unuttum", email doğrulama
- İnce yetki kontrolü (owner vs staff farkı endpoint bazında uygulanmayacak)
- `tenant_features` kontrolü (bir tenant'ın `classic_appointments` özelliğine sahip olup olmadığını şimdilik kontrol etme — bu ayrı bir task)
- Randevu güncelleme/iptal etme (`PATCH /appointments/:id`) — sadece oluşturma ve listeleme bu görevde

## Kabul Kriteri

Aşağıdaki akış, WhatsApp veya panel kullanılmadan, sadece `curl` ile uçtan uca çalışmalı:

1. `POST /auth/register` → yeni tenant + owner kullanıcı oluşur, token döner
2. `POST /auth/login` → aynı kullanıcıyla giriş, token döner
3. Token ile `POST /staff_members` → personel oluşturulur
4. Token ile `POST /services` → hizmet oluşturulur (örn. 60 dakika)
5. Token ile `POST /availability_rules` → çalışma saati tanımlanır (örn. Pazartesi 09:00-18:00)
6. Token ile `GET /availability/slots?staff_id=...&service_id=...&date=<bir pazartesi>` → boş slotlar listelenir (09:00, 10:00, 11:00...)
7. Token ile `POST /customers` → müşteri oluşturulur
8. Token ile `POST /appointments` (10:00 slotu için) → randevu **başarıyla** oluşturulur
9. Aynı personel + aynı saat için tekrar `POST /appointments` denenir → **409 Conflict** döner
10. `GET /appointments` → oluşturulan randevu listede görünür
11. **Farklı bir tenant'ın token'ıyla** aynı `GET /appointments` çağrısı yapılır → önceki tenant'ın randevusu **görünmez** (tenant izolasyonu doğrulanmış olur)
12. `core/` katmanındaki birim testleri (`pytest`) çalıştırılır, hepsi geçer

Bu 12 madde doğrulanmadan Faz 1 "tamamlandı" sayılmayacak. Her adımın `curl` komutu ve dönen yanıtı raporda gösterilmeli.
