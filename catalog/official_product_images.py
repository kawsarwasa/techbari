"""Curated official manufacturer sources for the TechBari demo catalog.

The management command downloads product-specific images into MEDIA_ROOT.  We keep
source pages here for provenance and only accept image hosts explicitly listed for
each manufacturer.
"""

OFFICIAL_PRODUCT_IMAGE_SOURCES = {
    "baseus": {
        "source_page": "https://cz.baseus.com/en/products/a00061900223-00",
        "allowed_hosts": ("baseus.com", "cdn.shopify.com"),
        "match_terms": ("baseus", "bowie", "e16", "a00061900223"),
        "direct_images": (),
    },
    "q20i": {
        "source_page": "https://www.soundcore.com/products/q20i-a3004z31",
        "allowed_hosts": ("soundcore.com", "soundcoreusa.myshopify.com", "cdn.shopify.com"),
        "match_terms": ("soundcore", "q20i", "a3004"),
        "direct_images": (
            "https://cdn.shopify.com/s/files/1/0519/2355/0368/files/A3004Z11_TD01_V1.jpg?v=1687317113",
            "https://cdn.shopify.com/s/files/1/0516/3761/6830/files/20251230-142814_3840x.png?v=1767076187",
        ),
    },
    "haylou": {
        "source_page": "https://haylou.com/products/haylou-rs4-plus",
        "allowed_hosts": ("haylou.com", "cdn.shopify.com"),
        "match_terms": ("haylou", "rs4", "plus"),
        "direct_images": (
            "https://haylou.com/cdn/shop/products/1_8453c5a9-fda0-4f8f-890b-c47d0822ecc2_large.jpg?v=1683353432",
            "https://haylou.com/cdn/shop/products/2_dbc82af7-d142-49dd-948d-4fa60a474788_large.jpg?v=1683353432",
            "https://haylou.com/cdn/shop/products/5_2379ae8c-c1db-4ef6-b1f7-e6f603b2f2b5_large.jpg?v=1683353432",
        ),
    },
    "jbl": {
        "source_page": "https://in.jbl.com/FLIP-6-.html?dwvar_FLIP-6-_color=Black-GLOBAL-Current",
        "allowed_hosts": ("jbl.com",),
        "match_terms": ("jbl", "flip6", "flip-6", "flip_6"),
        "direct_images": (
            "https://in.jbl.com/dw/image/v2/BFND_PRD/on/demandware.static/-/Sites-masterCatalog_Harman/default/dw4e91d6eb/1_JBL_FLIP6_HERO_BLACK_29391_x2.png?sh=1000&sw=1000",
            "https://in.jbl.com/dw/image/v2/BFND_PRD/on/demandware.static/-/Sites-masterCatalog_Harman/default/dw98ec93ec/3_JBL_FLIP6_FRONT_BLACK_29509_x2.png?sh=1000&sw=1000",
            "https://in.jbl.com/dw/image/v2/BFND_PRD/on/demandware.static/-/Sites-masterCatalog_Harman/default/dwd6724080/5_JBL_FLIP6_BACK_BLACK_29418_x2.png?sh=1000&sw=1000",
        ),
    },
    "xiaomi": {
        "source_page": "https://www.mi.com/in/product/xiaomi-power-bank-20000/",
        "allowed_hosts": ("mi.com", "appmifile.com"),
        "match_terms": ("xiaomi", "power", "bank", "20000"),
        "direct_images": (
            "https://i02.appmifile.com/389_operator_sg/10/07/2025/246048c3934eba8376a2c99e25401fd5.png",
        ),
    },
    "anker": {
        "source_page": "https://www.anker.com/ca/products/a2147",
        "allowed_hosts": ("anker.com", "cdn.shopify.com"),
        "match_terms": ("anker", "a2147", "511", "nano", "30w"),
        "direct_images": (
            "https://cdn.shopify.com/s/files/1/0743/7769/1325/files/SKU-04-Phantom_Black_18692dd7-dff0-4aa7-b86e-6337cf07a39f.png?v=1778667861",
            "https://cdn.shopify.com/s/files/1/0743/7769/1325/files/A2147111_TD02.jpg?v=1778667862",
            "https://cdn.shopify.com/s/files/1/0743/7769/1325/files/A2147121_TD06.jpg?v=1778667861",
        ),
    },
    "ugreen": {
        "source_page": "https://us.ugreen.com/products/ugreen-100w-usb-c-to-c-fast-charging-cable",
        "allowed_hosts": ("ugreen.com", "cdn.shopify.com"),
        "match_terms": ("ugreen", "100w", "usb", "cable"),
        "direct_images": (
            "https://us.ugreen.com/cdn/shop/files/ugreen-100w-usb-c-to-c-cable-pd-fast-charging-1084583.png?v=1752211808&width=1600",
        ),
    },
    "budsfe": {
        "source_page": "https://www.samsung.com/africa_en/audio-sound/galaxy-buds/galaxy-buds-fe-graphite-sm-r400nzaaxfa/",
        "allowed_hosts": ("samsung.com", "images.samsung.com"),
        "match_terms": ("galaxy", "buds", "fe", "r400"),
        "direct_images": (),
    },
    "neckband": {
        "source_page": "https://event.realme.com/in/realme-buds-wireless-3",
        "allowed_hosts": ("realme.com", "realme.net"),
        "match_terms": ("realme", "buds", "wireless", "3"),
        "direct_images": (),
        "allow_unmatched": True,
    },
    "amazfit": {
        "source_page": "https://in.amazfit.com/products/amazfit-bip-5",
        "allowed_hosts": ("amazfit.com", "cdn.shopify.com", "ucarecdn.com"),
        "match_terms": ("amazfit", "bip", "5"),
        "direct_images": (
            "https://in.amazfit.com/cdn/shop/products/2b88b81321c7510919fdfdbb9c69360e.jpg?v=1691659249",
        ),
    },
}
