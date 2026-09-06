#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/schema_listings.py — طبقة العرض: ما يراه الزائر قبل أن يحجز

الفصل الجوهري: `rooms` **مخزونٌ تشغيلي** — الغرفة ١٠١ مشغولة وتحتاج
تنظيفاً. والقائمة المعروضة شيءٌ آخر — «شاليه بمسبح · ٣ صور · ٨٠٠ ر.س
الليلة · على بُعد ٢ كم من الكورنيش». خلطُهما يعني أن تغيير حالة غرفةٍ
يُغيّر إعلاناً، وأن الزائر يرى أرقام الغرف ومن فيها.

    property_profile   هوية المنشأة المعروضة: اسم وشعار وصور ووصف وموقع
    listings           الوحدات المعروضة: نوعها وسعرها وسعتها ومرافقها
    listing_photos     صور كل وحدة بترتيبٍ يختاره المالك
    listing_units      ربط الوحدة المعروضة بغرف المخزون — للتوفّر الحقيقي

**التوفّر يُحسب من المخزون لا يُكتب يدوياً.** كتابته يدوياً يعني إعلاناً
يقول «متاح» وغرفةً مشغولة، فيصل الزائر ولا يجد مكاناً.
"""
from __future__ import annotations

import logging

log = logging.getLogger("dheuof.migrations")

#: أنواع الوحدات — مفرداتٌ مضبوطة لا نصٌّ حر.
#
# النصّ الحر يُنتج «شاليه» و«شالية» و«Chalet» في ثلاثة صفوف، فيبحث
# الزائر عن شاليه ولا يجد ثلثي المعروض. المسمّى العربي في الواجهة
# والمفتاح في القاعدة.
UNIT_KINDS = {
    "room":       "غرفة فندقية",
    "suite":      "جناح",
    "apartment":  "شقة",
    "chalet":     "شاليه",
    "resort":     "منتجع",
    "farm":       "مزرعة",
    "villa":      "فيلا",
    "camp":       "مخيّم",
    "rest_house": "استراحة",
}

#: المرافق — الحدّ الأدنى المشترك بين بوكينق وإكسبيديا وأقودا وجاذرن.
#
# قائمةٌ مضبوطة لأن البحث بالمرافق هو ما يُميّز تطبيق حجوزات عن جدول:
# «مسبح خاص + يسمح بالأطفال» سؤالٌ لا يُجاب من نصٍّ حر.
AMENITIES = {
    "wifi":         "واي فاي",
    "parking":      "موقف خاص",
    "pool":         "مسبح",
    "private_pool": "مسبح خاص",
    "kitchen":      "مطبخ",
    "ac":           "تكييف",
    "heating":      "تدفئة",
    "tv":           "تلفاز",
    "washer":       "غسالة",
    "bbq":          "منطقة شواء",
    "garden":       "حديقة",
    "gym":          "نادٍ رياضي",
    "breakfast":    "إفطار مشمول",
    "sea_view":     "إطلالة بحرية",
    "family_only":  "للعائلات فقط",
    "kids_ok":      "يسمح بالأطفال",
    "pets_ok":      "يسمح بالحيوانات",
    "accessible":   "مهيّأ لذوي الإعاقة",
    "smoking":      "يسمح بالتدخين",
    "elevator":     "مصعد",
    "workspace":    "ركن عمل",
    "crib":         "سرير أطفال",
}

# المسمّيات الإنجليزية — نفس المفاتيح كي تبقى القيمة المخزَّنة واحدة والعرض
# ثنائي اللغة. أي مفتاح ينقص هنا يعود إلى مسمّاه العربي (لا فراغ).
UNIT_KINDS_EN = {
    "room":       "Hotel room",
    "suite":      "Suite",
    "apartment":  "Apartment",
    "chalet":     "Chalet",
    "resort":     "Resort",
    "farm":       "Farm",
    "villa":      "Villa",
    "camp":       "Camp",
    "rest_house": "Rest house",
}

AMENITIES_EN = {
    "wifi":         "Wi-Fi",
    "parking":      "Private parking",
    "pool":         "Pool",
    "private_pool": "Private pool",
    "kitchen":      "Kitchen",
    "ac":           "Air conditioning",
    "heating":      "Heating",
    "tv":           "TV",
    "washer":       "Washer",
    "bbq":          "BBQ area",
    "garden":       "Garden",
    "gym":          "Gym",
    "breakfast":    "Breakfast included",
    "sea_view":     "Sea view",
    "family_only":  "Families only",
    "kids_ok":      "Children allowed",
    "pets_ok":      "Pets allowed",
    "accessible":   "Accessible",
    "smoking":      "Smoking allowed",
    "elevator":     "Elevator",
    "workspace":    "Workspace",
    "crib":         "Baby crib",
}


def kind_labels(lang: str = "ar") -> dict:
    """مسمّيات الأنواع باللغة المطلوبة، مع العربية أساساً تُكمّل النقص."""
    if str(lang).lower().startswith("en"):
        return {k: UNIT_KINDS_EN.get(k, v) for k, v in UNIT_KINDS.items()}
    return dict(UNIT_KINDS)


def amenity_labels(lang: str = "ar") -> dict:
    """مسمّيات المرافق باللغة المطلوبة، مع العربية أساساً تُكمّل النقص."""
    if str(lang).lower().startswith("en"):
        return {k: AMENITIES_EN.get(k, v) for k, v in AMENITIES.items()}
    return dict(AMENITIES)

LISTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS property_profile (
    client_id     VARCHAR(50) PRIMARY KEY,
    display_name  VARCHAR(200) NOT NULL,
    tagline       VARCHAR(300),
    description   TEXT,
    logo_url      TEXT,
    cover_url     TEXT,
    country       VARCHAR(80)  DEFAULT 'السعودية',
    city          VARCHAR(120),
    district      VARCHAR(120),
    address       TEXT,
    landmark      VARCHAR(200),
    landmark_km   NUMERIC(6,2),
    latitude      NUMERIC(10,7),
    longitude     NUMERIC(10,7),
    checkin_time  VARCHAR(10) DEFAULT '15:00',
    checkout_time VARCHAR(10) DEFAULT '12:00',
    phone         VARCHAR(30),
    is_published  BOOLEAN DEFAULT FALSE,
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_prof_city ON property_profile(country, city, district);
CREATE INDEX IF NOT EXISTS idx_prof_pub  ON property_profile(is_published);

CREATE TABLE IF NOT EXISTS listings (
    id            SERIAL PRIMARY KEY,
    client_id     VARCHAR(50) NOT NULL,
    kind          VARCHAR(20) NOT NULL,
    title         VARCHAR(200) NOT NULL,
    description   TEXT,
    base_price    NUMERIC(10,2) NOT NULL DEFAULT 0,
    weekend_price NUMERIC(10,2),
    capacity      INTEGER NOT NULL DEFAULT 2,
    bedrooms      INTEGER DEFAULT 1,
    bathrooms     INTEGER DEFAULT 1,
    area_sqm      INTEGER,
    amenities     JSONB DEFAULT '[]'::jsonb,
    min_nights    INTEGER DEFAULT 1,
    is_published  BOOLEAN DEFAULT FALSE,
    sort_order    INTEGER DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    CHECK (base_price >= 0),
    CHECK (capacity BETWEEN 1 AND 100),
    CHECK (min_nights BETWEEN 1 AND 365)
);
CREATE INDEX IF NOT EXISTS idx_listing_client ON listings(client_id);
CREATE INDEX IF NOT EXISTS idx_listing_pub    ON listings(client_id, is_published);
CREATE INDEX IF NOT EXISTS idx_listing_kind   ON listings(kind, is_published);
CREATE INDEX IF NOT EXISTS idx_listing_price  ON listings(base_price);
CREATE INDEX IF NOT EXISTS idx_listing_amen   ON listings USING GIN (amenities);

CREATE TABLE IF NOT EXISTS listing_photos (
    id          SERIAL PRIMARY KEY,
    listing_id  INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    client_id   VARCHAR(50) NOT NULL,
    url         TEXT NOT NULL,
    caption     VARCHAR(200),
    sort_order  INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_photo_listing ON listing_photos(listing_id, sort_order);

CREATE TABLE IF NOT EXISTS listing_units (
    listing_id  INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    room_id     INTEGER NOT NULL,
    client_id   VARCHAR(50) NOT NULL,
    PRIMARY KEY (listing_id, room_id)
);
CREATE INDEX IF NOT EXISTS idx_lunit_client ON listing_units(client_id)
"""


def run_listing_migrations(db) -> None:
    """
    يُنشئ جداول طبقة العرض.

    الفشل يُرفع ولا يُبتلع: جدولٌ ناقص يعني بوابةً تعرض صفراً بلا أن
    يعلم أحد، وهي السابقة نفسها التي كلّفت هذا المستودع.
    """
    if not getattr(db, "use_postgres", False):
        return
    made = 0
    for stmt in LISTINGS_SCHEMA.split(";"):
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            db.execute(stmt)
            made += 1
        except Exception as exc:
            log.error("فشل إنشاء جدول عرض: %s — %s", stmt.split("\n")[0][:60], exc)
            raise
    log.info("جداول العرض: %s عبارة نُفّذت", made)
