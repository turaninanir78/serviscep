# Rapor Formatı Kuralı

Her görevi bitirdiğinde, ayrıntılı işlem adımlarını (hangi
komutu çalıştırdığın, hangi dosyayı düzenlediğin) SADECE
konuşma akışında kısaca belirt. Ama en sona, ayrı ve net bir
başlık altında ("## Özet" gibi) şunları içeren KISA bir özet
ekle:

- Ne değişti (madde madde, en fazla 5-6 madde)
- Hangi dosyalar değişti (sadece isimler)
- Kabul kriteri karşılandı mı (evet/hayır, tek satır)
- Commit atıldı mı, hash'i ne
- Sıradaki adım için bilinmesi gereken tek bir not (varsa)

Bu özet, kullanıcının başka bir yere (örneğin bir denetim
aracına) doğrudan kopyala-yapıştır yapabileceği şekilde, kod
bloğu içinde, sade metin olarak yazılmalı — teknik jargon veya
uzun açıklama olmadan.

# CI (GitHub Actions)

`.github/workflows/ci.yml`, `master`'a her push'ta ve her pull
request'te otomatik tetiklenir — iki paralel job çalıştırır:
`backend` (Postgres service container + `pytest`) ve `frontend`
(`npm test` + `npm run build`). Sonuç, ilgili commit'in veya
PR'ın yanındaki durum simgesinden ya da repo'nun GitHub'daki
"Actions" sekmesinden görülebilir.
