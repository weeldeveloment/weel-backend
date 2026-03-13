# Apartment yaratish — API (frontend format qo‘llab-quvvatlanadi)

Backend frontend yuboradigan body formatini qabul qiladi.

## 1. `price`

**Qabul qilinadi:**
- Bitta raqam: `"price": 10` yoki `"price": 99.99`
- Ro‘yxat (Cottages formatida): `"price": [{"month_from": "...", "month_to": "...", "price_per_person": 10, "price_on_working_days": 1, "price_on_weekends": 1}, ...]`  
  Apartment uchun **birinchi elementning `price_per_person`** qiymati asosiy narx sifatida ishlatiladi.

Shuning uchun frontend barcha property type’lar uchun bir xil `price` ro‘yxatini yuborishi mumkin; Apartment uchun backend avtomatik bitta raqamga aylantiradi.

## 2. `property_services`

Frontend barcha tanlangan xizmatlar ro‘yxatini yuborishi mumkin. Backend **faqat shu property type (Apartment) ga tegishli xizmatlarni** saqlaydi, qolganlari e’tiborsiz qolinadi. Xato chiqarilmaydi.

Agar faqat to‘g‘ri xizmatlar chiqishini xohlasangiz:  
`GET /api/property/services/?property_type_id=<APARTMENT_TYPE_GUID>`

## Qisqacha

| Maydon               | Apartment uchun                                                                 |
|----------------------|---------------------------------------------------------------------------------|
| `price`              | Bitta raqam yoki ro‘yxat (ro‘yxat bo‘lsa birinchi elementning `price_per_person` ishlatiladi) |
| `property_services`  | Ixtiyoriy ro‘yxat; faqat Apartment type’ga tegishli xizmatlar saqlanadi          |
