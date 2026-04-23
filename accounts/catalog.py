from accounts.models import PackageCatalog
defaults = [
    ("launch-starter","Launch Starter",  79900,  "one-time"),
    ("business-essentials","Business Essentials",149900,"one-time"),
    ("growth-plus","Growth Plus",        239900, "one-time"),
    ("care-basic","Care Basic (Monthly)", 3900,  "subscription"),
    ("care-plus","Care Plus (Monthly)",   7900,  "subscription"),
    ("care-pro","Care Pro (Monthly)",    14900,  "subscription"),
]
for slug,name,price,type_ in defaults:
    PackageCatalog.objects.get_or_create(slug=slug, defaults={"name":name,"price_cents":price,"type":type_})
