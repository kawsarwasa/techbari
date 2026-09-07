from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Customer, CustomerGroup


class CustomerError(ValidationError):
    pass


@transaction.atomic
def delete_customer(*, customer):
    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    if getattr(customer, "sales_orders", None) is not None and customer.sales_orders.exists():
        raise CustomerError("Customers with sales history cannot be deleted. Set the customer inactive instead.")
    customer.delete()


@transaction.atomic
def delete_customer_group(*, group):
    group = CustomerGroup.objects.select_for_update().get(pk=group.pk)
    if group.customers.exists():
        raise CustomerError("Customer groups in use cannot be deleted. Set the group inactive instead.")
    group.delete()
