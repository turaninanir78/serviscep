from pydantic import BaseModel, ConfigDict


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TenantWhatsAppConnect(BaseModel):
    phone_number_id: str
    access_token: str
    business_account_id: str | None = None


class TenantWhatsAppConnectResponse(BaseModel):
    # Ham token'i ASLA geri dondurmez - sadece baglantinin kaydedildigini
    # dogrular.
    status: str = "connected"
    phone_number_id: str
