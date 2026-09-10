from pydantic import BaseModel, ConfigDict


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    # Web/mobil, randevu saat/tarihlerini (backend'in urettigi UTC instant'lari)
    # cihazin yerel saat dilimi yerine BU alanla goruntulemeli - aksi halde
    # farkli bir ulkedeki kullanici gun sinirinda yanlis gun/saat gorebilir.
    timezone: str


class TenantWhatsAppConnect(BaseModel):
    phone_number_id: str
    access_token: str
    business_account_id: str | None = None


class TenantWhatsAppConnectResponse(BaseModel):
    # Ham token'i ASLA geri dondurmez - sadece baglantinin kaydedildigini
    # dogrular.
    status: str = "connected"
    phone_number_id: str
