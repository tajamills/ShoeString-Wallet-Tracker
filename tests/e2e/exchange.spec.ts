import { test, expect } from '@playwright/test';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'https://tax-report-crypto.preview.emergentagent.com';

/**
 * Helper function to accept Terms of Service modal if it appears
 */
async function acceptTermsIfVisible(page: any) {
  const termsModal = page.locator('[role="dialog"]').filter({ hasText: /Terms of Service/i });
  if (await termsModal.isVisible({ timeout: 2000 }).catch(() => false)) {
    const scrollArea = page.locator('[data-radix-scroll-area-viewport]').first();
    if (await scrollArea.isVisible().catch(() => false)) {
      for (let i = 0; i < 5; i++) {
        await scrollArea.evaluate((el: any) => { el.scrollTop = el.scrollHeight; });
        await page.waitForTimeout(300);
      }
    }
    await page.getByTestId('terms-checkbox').click({ force: true });
    await page.waitForTimeout(300);
    await page.getByTestId('accept-terms-btn').click({ force: true });
    await page.waitForTimeout(500);
  }
}

/**
 * Helper function to login with the premium test user
 */
async function loginAsPremiumUser(page: any) {
  await page.getByTestId('login-button').click();
  await page.waitForSelector('[role="dialog"]');
  await page.getByTestId('email-input').fill('taxtest@test.com');
  await page.getByTestId('password-input').fill('TestPass123!');
  await page.getByTestId('auth-submit-button').click();
  await expect(page.getByTestId('user-info-bar')).toBeVisible({ timeout: 10000 });
  await acceptTermsIfVisible(page);
}

test.describe('Exchange CSV Import API Tests', () => {
  test('GET /api/exchanges/supported returns 6 supported exchanges', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/exchanges/supported`);
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.exchanges).toBeDefined();
    expect(data.exchanges.length).toBe(6);
    
    const exchangeIds = data.exchanges.map((ex: any) => ex.id);
    expect(exchangeIds).toContain('coinbase');
    expect(exchangeIds).toContain('binance');
    expect(exchangeIds).toContain('kraken');
    expect(exchangeIds).toContain('gemini');
    expect(exchangeIds).toContain('crypto_com');
    expect(exchangeIds).toContain('kucoin');
    
    // Verify structure - now has instructions instead of auth_type
    for (const exchange of data.exchanges) {
      expect(exchange.id).toBeDefined();
      expect(exchange.name).toBeDefined();
      expect(exchange.instructions).toBeDefined();
    }
  });

  test('GET /api/exchanges/export-instructions returns detailed steps', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/exchanges/export-instructions/coinbase`);
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.name).toBe('Coinbase');
    expect(data.steps).toBeDefined();
    expect(Array.isArray(data.steps)).toBe(true);
    expect(data.steps.length).toBeGreaterThan(0);
    expect(data.notes).toBeDefined();
  });

  test('GET /api/exchanges/supported returns accepted_columns for each exchange', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/exchanges/supported`);
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.exchanges).toBeDefined();
    
    // Each exchange should have accepted_columns field
    for (const exchange of data.exchanges) {
      expect(exchange.accepted_columns).toBeDefined();
      expect(Array.isArray(exchange.accepted_columns)).toBe(true);
    }
    
    // Coinbase specifically should show multiple formats
    const coinbase = data.exchanges.find((ex: any) => ex.id === 'coinbase');
    expect(coinbase).toBeDefined();
    expect(coinbase.accepted_columns.length).toBeGreaterThanOrEqual(2);
    
    // Should mention both classic and modern formats
    const columnText = coinbase.accepted_columns.join(' ').toLowerCase();
    expect(columnText).toContain('classic');
    expect(columnText).toContain('modern');
  });

  test('GET /api/exchanges/export-instructions/coinbase returns accepted_columns', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/exchanges/export-instructions/coinbase`);
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.accepted_columns).toBeDefined();
    expect(Array.isArray(data.accepted_columns)).toBe(true);
    expect(data.accepted_columns.length).toBeGreaterThan(0);
    
    // Should describe expected CSV column formats
    const columnsText = data.accepted_columns.join(' ').toLowerCase();
    expect(columnsText).toMatch(/timestamp|transaction/i);
  });

  test('Free user API request to import CSV returns 403', async ({ request }) => {
    const uniqueId = Date.now();
    const testEmail = `TEST_exchange_csv_${uniqueId}@test.com`;
    
    const registerResponse = await request.post(`${API_URL}/api/auth/register`, {
      data: { email: testEmail, password: 'TestPass123!' }
    });
    
    expect(registerResponse.status()).toBe(200);
    const { access_token } = await registerResponse.json();
    
    // Create a mock CSV file
    const csvContent = 'Timestamp,Transaction Type,Asset,Quantity Transacted\n2024-01-01,Buy,BTC,0.1';
    const formData = new FormData();
    formData.append('file', new Blob([csvContent], { type: 'text/csv' }), 'test.csv');
    
    const importResponse = await request.post(`${API_URL}/api/exchanges/import-csv`, {
      headers: { Authorization: `Bearer ${access_token}` },
      multipart: {
        file: {
          name: 'test.csv',
          mimeType: 'text/csv',
          buffer: Buffer.from(csvContent)
        }
      }
    });
    
    expect(importResponse.status()).toBe(403);
    const errorData = await importResponse.json();
    expect(errorData.detail).toContain('Unlimited');
  });

  test('Free user API request to get transactions returns 403', async ({ request }) => {
    const uniqueId = Date.now();
    const testEmail = `TEST_exchange_tx_${uniqueId}@test.com`;
    
    const registerResponse = await request.post(`${API_URL}/api/auth/register`, {
      data: { email: testEmail, password: 'TestPass123!' }
    });
    
    expect(registerResponse.status()).toBe(200);
    const { access_token } = await registerResponse.json();
    
    const txResponse = await request.get(`${API_URL}/api/exchanges/transactions`, {
      headers: { Authorization: `Bearer ${access_token}` }
    });
    
    expect(txResponse.status()).toBe(403);
  });
});

test.describe('Exchange UI Tests - Unlimited Users', () => {
  test('Exchange button visible for Unlimited users', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await loginAsPremiumUser(page);
    
    // Unlimited user should see Exchange button
    await expect(page.getByTestId('exchange-button')).toBeVisible();
  });

  test('Exchange modal opens with Import and Tax Calculator tabs', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await loginAsPremiumUser(page);
    
    // Open Exchange modal
    await page.getByTestId('exchange-button').click();
    await expect(page.getByTestId('exchange-modal')).toBeVisible({ timeout: 5000 });
    
    // Modal should show "Exchange Data" title
    await expect(page.locator('text=Exchange Data')).toBeVisible();
    
    // Should have two tabs: Import CSVs and Tax Calculator
    await expect(page.getByTestId('tab-import')).toBeVisible();
    await expect(page.getByTestId('tab-tax')).toBeVisible();
    
    // Upload button should be visible (Import tab is active by default)
    await expect(page.getByTestId('upload-csv-button')).toBeVisible();
    
    // Privacy note about no API keys should be visible
    await expect(page.locator('text=no API keys')).toBeVisible();
  });

  test('Exchange modal shows all 6 supported exchanges', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await loginAsPremiumUser(page);
    
    // Open Exchange modal
    await page.getByTestId('exchange-button').click();
    await expect(page.getByTestId('exchange-modal')).toBeVisible({ timeout: 5000 });
    
    // All exchanges should be visible
    await expect(page.locator('text=Coinbase')).toBeVisible();
    await expect(page.locator('text=Binance')).toBeVisible();
    await expect(page.locator('text=Kraken')).toBeVisible();
    await expect(page.locator('text=Gemini')).toBeVisible();
    await expect(page.locator('text=Crypto.com')).toBeVisible();
    await expect(page.locator('text=KuCoin')).toBeVisible();
    
    // Each exchange should have "How to export" hint
    const howToExportHints = page.locator('text=How to export');
    await expect(howToExportHints).toHaveCount(6);
  });

  test('Click exchange card shows export instructions', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await loginAsPremiumUser(page);
    
    // Open Exchange modal
    await page.getByTestId('exchange-button').click();
    await expect(page.getByTestId('exchange-modal')).toBeVisible({ timeout: 5000 });
    
    // Click Coinbase card to show instructions
    await page.locator('text=Coinbase').first().click();
    
    // Instructions should expand and show steps
    await expect(page.locator('text=Log in to Coinbase')).toBeVisible({ timeout: 3000 });
  });
});

test.describe('Exchange UI Tests - Free Users', () => {
  test('Free user does not see Exchange button', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    
    // Create a new free user
    const uniqueId = Date.now();
    const testEmail = `TEST_exchange_free_${uniqueId}@test.com`;
    const testPassword = 'TestPass123!';
    
    // Click login button
    await page.getByTestId('login-button').click();
    await page.waitForSelector('[role="dialog"]');
    
    // Click "Don't have an account? Sign up" link
    await page.getByText(/don't have an account/i).click();
    
    // Fill registration form
    await page.getByTestId('email-input').fill(testEmail);
    await page.getByTestId('password-input').fill(testPassword);
    
    // Click Sign Up button
    await page.getByTestId('auth-submit-button').click();
    
    // Wait for login
    await expect(page.getByTestId('user-info-bar')).toBeVisible({ timeout: 10000 });
    
    // Accept terms if visible
    await acceptTermsIfVisible(page);
    
    // Free user should NOT see Exchange button (only shown for Unlimited)
    await expect(page.getByTestId('exchange-button')).not.toBeVisible();
    
    // Free user should see Upgrade button
    await expect(page.getByTestId('upgrade-button')).toBeVisible();
  });
});

test.describe('Exchange Tax Calculator Tab Tests', () => {
  test('Tax Calculator tab shows when clicked', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await loginAsPremiumUser(page);
    
    // Open Exchange modal
    await page.getByTestId('exchange-button').click();
    await expect(page.getByTestId('exchange-modal')).toBeVisible({ timeout: 5000 });
    
    // Click Tax Calculator tab
    await page.getByTestId('tab-tax').click();
    
    // Exchange Tax Calculator component should be visible
    await expect(page.getByTestId('exchange-tax-calculator')).toBeVisible({ timeout: 5000 });
    
    // Tax Calculator title should be visible
    await expect(page.locator('text=Exchange Tax Calculator')).toBeVisible();
  });

  test('Tax Calculator shows no data message when empty', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await loginAsPremiumUser(page);
    
    // Open Exchange modal
    await page.getByTestId('exchange-button').click();
    await expect(page.getByTestId('exchange-modal')).toBeVisible({ timeout: 5000 });
    
    // Click Tax Calculator tab
    await page.getByTestId('tab-tax').click();
    await expect(page.getByTestId('exchange-tax-calculator')).toBeVisible({ timeout: 5000 });
    
    // Should either show data cards OR "No Exchange Data Yet" message
    const noDataMessage = page.locator('text=No Exchange Data Yet');
    const dataCards = page.locator('text=Total Realized Gains');
    
    // Wait for either to appear
    await expect(noDataMessage.or(dataCards)).toBeVisible({ timeout: 5000 });
  });

  test('Tax Calculator has year and asset filters', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await loginAsPremiumUser(page);
    
    // Open Exchange modal
    await page.getByTestId('exchange-button').click();
    await expect(page.getByTestId('exchange-modal')).toBeVisible({ timeout: 5000 });
    
    // Click Tax Calculator tab
    await page.getByTestId('tab-tax').click();
    await expect(page.getByTestId('exchange-tax-calculator')).toBeVisible({ timeout: 5000 });
    
    // Year filter should be visible - it's a select dropdown with years
    const yearSelect = page.locator('select').filter({ hasText: /All Years|2026|2025|2024/ }).first();
    await expect(yearSelect).toBeVisible();
    
    // Refresh button should be visible
    const refreshButton = page.locator('button').filter({ has: page.locator('[class*="refresh"]').or(page.locator('svg')) }).first();
    await expect(refreshButton).toBeVisible();
  });

  test('Switching between Import and Tax Calculator tabs works', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await loginAsPremiumUser(page);
    
    // Open Exchange modal
    await page.getByTestId('exchange-button').click();
    await expect(page.getByTestId('exchange-modal')).toBeVisible({ timeout: 5000 });
    
    // Verify Import tab content
    await expect(page.getByTestId('upload-csv-button')).toBeVisible();
    await expect(page.locator('text=Supported Exchanges')).toBeVisible();
    
    // Switch to Tax Calculator tab
    await page.getByTestId('tab-tax').click();
    await expect(page.getByTestId('exchange-tax-calculator')).toBeVisible({ timeout: 5000 });
    
    // Import content should be hidden now
    await expect(page.getByTestId('upload-csv-button')).not.toBeVisible();
    
    // Switch back to Import tab
    await page.getByTestId('tab-import').click();
    
    // Import content should be visible again
    await expect(page.getByTestId('upload-csv-button')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=Supported Exchanges')).toBeVisible();
  });
});

test.describe('Exchange Tax API Tests', () => {
  test('POST /api/exchanges/tax/calculate requires auth', async ({ request }) => {
    const response = await request.post(`${API_URL}/api/exchanges/tax/calculate`, {
      data: {}
    });
    expect(response.status()).toBe(403);
  });

  test('GET /api/exchanges/tax/form-8949 requires auth', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/exchanges/tax/form-8949`);
    expect(response.status()).toBe(403);
  });

  test('Free user gets 403 on tax/calculate endpoint', async ({ request }) => {
    const uniqueId = Date.now();
    const testEmail = `TEST_exchange_taxcalc_${uniqueId}@test.com`;
    
    const registerResponse = await request.post(`${API_URL}/api/auth/register`, {
      data: { email: testEmail, password: 'TestPass123!' }
    });
    
    expect(registerResponse.status()).toBe(200);
    const { access_token } = await registerResponse.json();
    
    const taxResponse = await request.post(`${API_URL}/api/exchanges/tax/calculate`, {
      headers: { Authorization: `Bearer ${access_token}` },
      data: {}
    });
    
    expect(taxResponse.status()).toBe(403);
    const errorData = await taxResponse.json();
    expect(errorData.detail).toContain('Unlimited');
  });

  test('Free user gets 403 on form-8949 endpoint', async ({ request }) => {
    const uniqueId = Date.now();
    const testEmail = `TEST_exchange_form8949_${uniqueId}@test.com`;
    
    const registerResponse = await request.post(`${API_URL}/api/auth/register`, {
      data: { email: testEmail, password: 'TestPass123!' }
    });
    
    expect(registerResponse.status()).toBe(200);
    const { access_token } = await registerResponse.json();
    
    const formResponse = await request.get(`${API_URL}/api/exchanges/tax/form-8949`, {
      headers: { Authorization: `Bearer ${access_token}` }
    });
    
    expect(formResponse.status()).toBe(403);
    const errorData = await formResponse.json();
    expect(errorData.detail).toContain('Unlimited');
  });

  test('Free user gets 403 on form-8949/csv endpoint', async ({ request }) => {
    const uniqueId = Date.now();
    const testEmail = `TEST_exchange_csv_${uniqueId}@test.com`;
    
    const registerResponse = await request.post(`${API_URL}/api/auth/register`, {
      data: { email: testEmail, password: 'TestPass123!' }
    });
    
    expect(registerResponse.status()).toBe(200);
    const { access_token } = await registerResponse.json();
    
    const csvResponse = await request.get(`${API_URL}/api/exchanges/tax/form-8949/csv`, {
      headers: { Authorization: `Bearer ${access_token}` }
    });
    
    expect(csvResponse.status()).toBe(403);
    const errorData = await csvResponse.json();
    expect(errorData.detail).toContain('Unlimited');
  });
});
