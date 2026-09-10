(() => {
  function initShipmentAdd() {
    const form = document.getElementById('shipmentAddForm');
    const orderSelect = document.getElementById('id_order');
    const courierSelect = document.getElementById('id_courier');
    const courierFee = document.getElementById('id_courier_fee');
    const codExpected = document.getElementById('id_cod_expected');
    const customerShipping = document.getElementById('shipmentCustomerShippingCharge');
    const orderOutstanding = document.getElementById('shipmentOrderOutstanding');
    const codNote = document.getElementById('shipmentCodNote');
    const headerOrder = document.getElementById('shipmentHeaderOrder');
    const summaryOrder = document.getElementById('shipmentSummaryOrder');
    const summaryTotal = document.getElementById('shipmentSummaryTotal');
    const summaryShipping = document.getElementById('shipmentSummaryShipping');
    const summaryOutstanding = document.getElementById('shipmentSummaryOutstanding');
    const summaryCod = document.getElementById('shipmentSummaryCod');
    if (!form || !orderSelect || !courierSelect) return;

    const money = (value) => {
      const amount = Number(value || 0);
      return `৳ ${amount.toLocaleString('en-BD', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    };

    function selectedOption(select) {
      return select.options[select.selectedIndex] || null;
    }

    function syncOrder() {
      const option = selectedOption(orderSelect);
      const outstanding = option?.dataset.outstanding ?? '';
      const shippingCharge = option?.dataset.shippingCharge ?? '';
      const grandTotal = option?.dataset.grandTotal ?? '';
      const orderLabel = option?.value ? option.textContent.trim() : '—';

      if (customerShipping) customerShipping.value = option?.value ? money(shippingCharge) : '—';
      if (orderOutstanding) orderOutstanding.value = option?.value ? money(outstanding) : '—';
      if (codExpected) codExpected.value = option?.value ? Number(outstanding || 0).toFixed(2) : '';
      if (headerOrder) headerOrder.textContent = orderLabel;
      if (summaryOrder) summaryOrder.textContent = orderLabel;
      if (summaryTotal) summaryTotal.textContent = option?.value ? money(grandTotal) : '—';
      if (summaryShipping) summaryShipping.textContent = option?.value ? money(shippingCharge) : '—';
      if (summaryOutstanding) summaryOutstanding.textContent = option?.value ? money(outstanding) : '—';
      if (summaryCod) summaryCod.textContent = option?.value ? money(outstanding) : '—';

      syncCodNote();
    }

    function syncCourier(forceDefault = false) {
      const option = selectedOption(courierSelect);
      if (!option?.value) return;
      const defaultFee = option.dataset.defaultFee ?? '';
      if (courierFee && (forceDefault || !courierFee.value.trim())) {
        courierFee.value = Number(defaultFee || 0).toFixed(2);
      }
      syncCodNote();
    }

    function syncCodNote() {
      if (!codNote) return;
      const orderOption = selectedOption(orderSelect);
      const courierOption = selectedOption(courierSelect);
      const outstanding = Number(orderOption?.dataset.outstanding || 0);
      const supportsCod = courierOption?.dataset.supportsCod !== '0';

      if (!orderOption?.value) {
        codNote.textContent = 'Select a Sales Order to calculate the remaining amount the courier should collect.';
        return;
      }
      if (outstanding <= 0) {
        codNote.textContent = 'This order has no outstanding balance, so COD collection is not required.';
        return;
      }
      if (courierOption?.value && !supportsCod) {
        codNote.textContent = 'This order has an outstanding balance, but the selected courier is not configured for COD.';
        return;
      }
      codNote.textContent = `Courier should collect ${money(outstanding)} from the customer. This value is auto-calculated from the order outstanding amount.`;
    }

    orderSelect.addEventListener('change', syncOrder);
    courierSelect.addEventListener('change', () => syncCourier(true));

    syncOrder();
    syncCourier(form.dataset.bound !== '1');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initShipmentAdd);
  } else {
    initShipmentAdd();
  }
})();
