# Claude Code Görevi 01 — Docker Geliştirme Ortamı (Postgres + Backend + Frontend)

## Bağlam

`docs/architecture.md` bu projenin ana mimari referansıdır — kabul et ve uygula.
Faz 1 kapsamı bu belgede tanımlı: randevu motoru henüz yazılmıyor, bu görev sadece **üç servisin birlikte ayağa kalktığını doğrulayan** minimal bir iskelet kurmak.

## Yapılacaklar

1. Proje kök dizininde şu klasör yapısını oluştur:
   ```
   serviscep/
   ├── backend/
   │   └── app/
   │       └── main.py
   ├── frontend/            (Next.js create-next-app ile, TypeScript)
   ├── docker-compose.yml
   ├── .env.example
   └── docs/architecture.md   (zaten var, dokunma)
   ```

2. **Backend (FastAPI) — minimal, iş mantığı YOK:**
   - Tek endpoint: `GET /health`
   - Bu endpoint (a) servisin ayakta olduğunu, (b) PostgreSQL'e bağlanabildiğini doğrulayan basit bir sorgu (`SELECT 1`) çalıştırıp sonucu döner.
   - `tenants`, `users`, `appointments` gibi hiçbir model, tablo veya migration oluşturma — henüz veri modeli yok, sadece bağlantı testi.
   - `requirements.txt` (veya `pyproject.toml`): fastapi, uvicorn, psycopg (veya asyncpg) — sadece bağlantı testi için gereken minimum.

3. **Frontend (Next.js + TypeScript) — minimal:**
   - `create-next-app` ile varsayılan proje.
   - Tek sayfa: backend'in `/health` endpoint'ine istek atıp sonucu ekranda gösteren basit bir ana sayfa (ör. "Backend: OK" / "Backend: unreachable").
   - Başka hiçbir sayfa, layout veya bileşen ekleme.

4. **PostgreSQL:**
   - Resmi `postgres` imajı (pgvector veya başka uzantı YOK — Faz 1 kapsamında değil, bkz. architecture.md Bölüm 3).
   - Volume ile veri kalıcılığı sağlanmalı (`docker compose down` sonrası veri kaybolmamalı).

5. **`docker-compose.yml`:**
   - Sadece üç servis: `postgres`, `backend`, `frontend`.
   - **n8n ve Redis EKLEME** — architecture.md Bölüm 9 ve Bölüm 15'e göre bu ikisi Faz 1'de gereksiz.
   - Servisler arası bağlantı: backend, `DATABASE_URL` ortam değişkeni üzerinden postgres'e; frontend, backend'e bir ortam değişkeni (`NEXT_PUBLIC_BACKEND_URL` gibi) üzerinden bağlansın — hardcoded URL kullanma.
   - `.env.example` dosyasında gereken tüm değişkenler örnek değerleriyle listelensin (gerçek `.env` git'e eklenmemeli, `.gitignore`'a ekle).

## Yapılmayacaklar (kapsam dışı — architecture.md'ye göre)

- Randevu sistemi, tenant/kullanıcı/personel modelleri — HİÇBİRİ
- Authentication / JWT
- n8n, Redis, pgvector
- Veritabanı migration aracı kurulumu (Alembic vb.) — şimdilik gerekmiyor, tek tablo bile yok
- Production/VDS ayarları — bu görev sadece local geliştirme ortamı

## Kabul Kriteri (test adımı)

```
docker compose up -d --build
```

çalıştırıldığında:

1. Üç container da `running`/`healthy` durumda olmalı (`docker compose ps` ile kontrol).
2. `curl http://localhost:<backend_port>/health` → hem "servis ayakta" hem "veritabanı bağlantısı başarılı" bilgisini dönmeli.
3. Tarayıcıda `http://localhost:<frontend_port>` açıldığında, sayfa backend'den aldığı health durumunu göstermeli (yani frontend → backend → postgres zinciri uçtan uca çalışıyor).
4. `docker compose down` ardından tekrar `docker compose up -d` yapıldığında postgres verisi (şu an boş olsa da) kalıcı olmalı — volume doğru tanımlanmış olmalı.

Bu dört madde doğrulanmadan bir sonraki aşamaya (veri modeli / randevu motoru) geçilmeyecek.
