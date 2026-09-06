// DOM interaction checks. jsdom is an optional test tool, never a frontend dependency.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { JSDOM } = require(process.argv[2] || 'jsdom');
const pages = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const root = path.resolve(__dirname, '..');
const code = Object.fromEntries(['store/js/app.js', 'admin/js/admin.js', 'admin/js/product-crud.js']
  .map(file => ['/static/' + file, fs.readFileSync(path.join(root, 'static', file), 'utf8')]));
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

async function load(url, storage = {}) {
  const dom = new JSDOM(pages[url], {url: 'http://localhost' + url, runScripts: 'outside-only', pretendToBeVisual: true});
  const w = dom.window, errors = [];
  w.addEventListener('error', e => errors.push(e.error || e.message));
  w.HTMLElement.prototype.scrollIntoView = () => {};
  w.matchMedia = () => ({matches: false, addListener() {}, removeListener() {}});
  w.confirm = () => true;
  w.URL.createObjectURL = () => 'blob:test';
  w.URL.revokeObjectURL = () => {};
  for (const [key, value] of Object.entries(storage)) w.localStorage.setItem(key, JSON.stringify(value));
  await new Promise(resolve => w.document.addEventListener('DOMContentLoaded', resolve, {once: true}));
  for (const script of w.document.querySelectorAll('script[src]')) w.eval(code[script.getAttribute('src')]);
  w.document.dispatchEvent(new w.Event('DOMContentLoaded'));
  assert.deepEqual(errors, [], 'Runtime errors on ' + url);
  const $ = selector => w.document.querySelector(selector);
  return {w, $, close: () => w.close(), click: selector => {assert.ok($(selector), selector); $(selector).click();},
    set: (selector, value) => {$(selector).value = value; $(selector).dispatchEvent(new w.Event('input', {bubbles: true}));},
    stored: key => JSON.parse(w.localStorage.getItem(key))};
}

(async () => {
  let count = 0;
  for (const url of Object.keys(pages)) {
    const app = await load(url);
    assert.ok(app.$('main'), url);
    if (url.startsWith('/product/')) {
      assert.ok(app.$('#mainProductImage').getAttribute('src').startsWith('/static/'));
      assert.ok(app.$('.swatch'), 'Variant missing on ' + url);
    }
    app.close(); count++;
  }
  let app = await load('/');
  assert.equal(app.w.document.querySelectorAll('#featuredGrid .product-card').length, 6);
  const hero = app.$('#heroTitle').textContent; app.click('#heroNext'); await pause(400);
  assert.notEqual(app.$('#heroTitle').textContent, hero);
  app.click('#featuredGrid [data-wish="baseus"]');
  assert.equal(app.stored('nu_wish').includes('baseus'), false);
  app.close();

  app = await load('/products/');
  assert.equal(app.w.document.querySelectorAll('#allProductsGrid .product-card').length, 20);
  app.set('#productSearch', 'UGREEN');
  assert.equal([...app.w.document.querySelectorAll('#allProductsGrid .product-card')].filter(c => c.style.display !== 'none').length, 1);
  app.click('#allProductsGrid [data-product="ugreen"]');
  assert.ok(app.stored('nu_cart').find(p => p.id === 'ugreen'));
  app.close();

  app = await load('/product/anker-soundcore-q20i-wireless-headphones/', {nu_cart: []});
  app.click('#productQtyPlus');app.click('#productAddToCart');
  assert.equal(app.stored('nu_cart')[0].id, 'q20i');assert.equal(app.stored('nu_cart')[0].qty, 2);
  app.click('#productZoomStage');assert.equal(app.$('#productLightbox').hidden, false);
  app.click('#productLightboxClose');assert.equal(app.$('#productLightbox').hidden, true);
  app.click('[data-product-tab="specifications"]');assert.ok(app.$('[data-product-panel="specifications"]').classList.contains('active'));
  app.close();

  app = await load('/cart/');
  app.click('[data-qty-plus]');assert.equal(app.stored('nu_cart')[0].qty, 2);
  app.click('[data-qty-minus]');assert.equal(app.stored('nu_cart')[0].qty, 1);
  app.set('#cartCouponInput', 'SAVE1000');app.click('#cartCouponApply');assert.equal(app.w.localStorage.getItem('nu_coupon'), 'SAVE1000');
  assert.equal(app.$('[data-cart-grand]').textContent, '৳ 11,670');
  app.click('[data-remove-cart]');await pause(250);assert.equal(app.stored('nu_cart').length, 2);
  app.click('#clearCart');assert.equal(app.stored('nu_cart').length, 0);assert.equal(app.$('#cartEmpty').hidden, false);app.close();

  app = await load('/checkout/');
  assert.equal(app.$('#shippingCharge').textContent, '৳ 60');app.click('[data-delivery="outside"]');
  assert.equal(app.$('#shippingCharge').textContent, '৳ 120');assert.equal(app.$('#checkoutGrand').textContent, '৳ 12,790');
  app.click('#placeOrder');assert.equal(app.$('#placeOrder').disabled, true);app.close();

  app = await load('/wishlist/');app.click('[data-remove-wish="baseus"]');assert.equal(app.stored('nu_wish').includes('baseus'), false);app.close();
  app = await load('/register/');assert.ok(app.$('[data-auth-view="register"]').classList.contains('active'));app.close();
  app = await load('/login/');app.$('#loginForm').dispatchEvent(new app.w.Event('submit', {bubbles: true, cancelable: true}));
  assert.ok(app.$('#loginMessage').textContent.includes('Please enter'));app.close();

  app = await load('/dashboard/products/');
  assert.equal(app.w.document.querySelectorAll('#productRows tr').length, 10);
  app.click('[data-product-delete="1"]');assert.equal(app.$('#productDeleteOverlay').hidden, false);
  app.click('#confirmProductDelete');assert.equal(app.stored('techbari_admin_products').length, 9);app.close();
  app = await load('/dashboard/products/', {techbari_admin_products: []});
  assert.equal(app.stored('techbari_admin_products').length, 0);assert.ok(app.$('#productRows').textContent.includes('No products'));app.close();
  app = await load('/dashboard/customers/detail/?id=999&local=1', {techbari_admin_customers: [{id:999,name:'Local Customer',email:'local@example.test',phone:'01700000000',orders:0,spent:0,group:'Regular'}]});
  assert.equal(app.$('h1').textContent, 'Local Customer');app.close();
  app = await load('/dashboard/orders/detail/?id=999&local=1', {techbari_admin_orders: [{id:999,orderId:'#LOCAL999',customer:'Local Customer',items:'Local Item',amount:1234,status:'Pending',payment:'Cash',date:'2026-09-06'}]});
  assert.equal(app.$('h1').textContent, 'Order #LOCAL999');assert.ok(app.$('[data-detail-key="amount"]').textContent.includes('1,234'));app.close();
  app = await load('/dashboard/products/add/');app.set('[name="name"]', 'Validation Product');
  app.$('#productAddForm').dispatchEvent(new app.w.Event('submit', {bubbles: true, cancelable: true}));
  assert.ok(app.stored('techbari_admin_products').find(p => p.name === 'Validation Product'));app.close();
  app = await load('/dashboard/products/edit/');app.set('[name="name"]', 'Edited Product');
  app.$('#productEditForm').dispatchEvent(new app.w.Event('submit', {bubbles: true, cancelable: true}));
  assert.equal(app.stored('techbari_admin_products')[0].name, 'Edited Product');app.close();

  for (const [url, entity] of [['customers', 'customers'], ['suppliers', 'suppliers'], ['coupons', 'coupons']]) {
    app = await load('/dashboard/' + url + '/add/');
    const form = app.$('[data-crud-form]');
    form.dispatchEvent(new app.w.Event('submit', {bubbles: true, cancelable: true}));
    assert.ok(app.stored('techbari_admin_' + entity).length > 2);app.close();
  }
  app = await load('/dashboard/pos/');
  assert.equal(app.w.document.querySelectorAll('[data-pos-add]').length, 12);
  const total = app.$('[data-pos-total]').textContent;app.click('[data-pos-plus="101"]');assert.notEqual(app.$('[data-pos-total]').textContent, total);
  app.click('[data-pos-payment="bKash"]');assert.ok(app.$('[data-pos-payment="bKash"]').classList.contains('active'));
  app.set('[data-pos-search]', 'JBL');assert.equal(app.w.document.querySelectorAll('[data-pos-add]').length, 1);
  app.click('[data-pos-complete]');assert.ok(app.$('[data-pos-cart]').textContent.includes('No products'));app.close();
  console.log('PASS: JavaScript initializes on ' + count + ' URLs.');
  console.log('PASS: slider, search, wishlist, gallery, cart, coupon, delivery, auth validation, product CRUD, empty catalog persistence, customer/supplier/coupon creation, POS controls.');
})().catch(error => {console.error(error);process.exit(1);});
