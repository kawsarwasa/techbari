from django.db import transaction

from .models import ProductImage, ProductSpecification


def replace_specifications(product, names, values):
    rows = []
    seen = set()
    for index, (name, value) in enumerate(zip(names, values)):
        name = (name or "").strip()
        value = (value or "").strip()
        if not name or not value or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        rows.append(ProductSpecification(product=product, name=name, value=value, sort_order=index))
    ProductSpecification.objects.filter(product=product).delete()
    if rows:
        ProductSpecification.objects.bulk_create(rows)


def add_product_images(product, uploads):
    existing_primary = ProductImage.objects.filter(product=product, role=ProductImage.Role.PRIMARY).exists()
    start = ProductImage.objects.filter(product=product).count()
    for offset, upload in enumerate(uploads):
        role = ProductImage.Role.GALLERY
        if not existing_primary and offset == 0:
            role = ProductImage.Role.PRIMARY
            existing_primary = True
        ProductImage.objects.create(product=product, image=upload, alt_text=product.name, role=role, sort_order=start + offset)


def save_product_bundle(form, image_files, spec_names, spec_values):
    with transaction.atomic():
        product = form.save()
        replace_specifications(product, spec_names, spec_values)
        if image_files:
            add_product_images(product, image_files)
        return product
