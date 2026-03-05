import { test, expect } from '@playwright/test';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'https://wallet-tax-hub.preview.emergentagent.com';

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

test.describe('Exchange API Tests', () => {
  test('GET /api/exchanges/supported returns Coinbase and Binance', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/exchanges/supported`);
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.exchanges).toBeDefined();
    expect(data.exchanges.length).toBeGreaterThanOrEqual(2);
    
    const exchangeIds = data.exchanges.map((ex: any) => ex.id);
    expect(exchangeIds).toContain('coinbase');
    expect(exchangeIds).toContain('binance');
    
    // Verify structure
    for (const exchange of data.exchanges) {
      expect(exchange.id).toBeDefined();
      expect(exchange.name).toBeDefined();
      expect(exchange.auth_type).toBeDefined();
      expect(exchange.description).toBeDefined();
      expect(exchange.features).toBeDefined();
    }
  });

  test('Free user API request to connect exchange returns 403', async ({ request }) => {
    const uniqueId = Date.now();
    const testEmail = `TEST_exchange_api_${uniqueId}@test.com`;
    
    const registerResponse = await request.post(`${API_URL}/api/auth/register`, {
      data: { email: testEmail, password: 'TestPass123!' }
    });
    
    expect(registerResponse.status()).toBe(200);
    const { access_token } = await registerResponse.json();
    
    const connectResponse = await request.post(`${API_URL}/api/exchanges/connect`, {
      headers: { Authorization: `Bearer ${access_token}` },
      data: { exchange: 'coinbase', access_token: 'fake_token' }
    });
    
    expect(connectResponse.status()).toBe(403);
    const errorData = await connectResponse.json();
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

  test('Free user API request to sync exchange returns 403', async ({ request }) => {
    const uniqueId = Date.now();
    const testEmail = `TEST_exchange_sync_${uniqueId}@test.com`;
    
    const registerResponse = await request.post(`${API_URL}/api/auth/register`, {
      data: { email: testEmail, password: 'TestPass123!' }
    });
    
    expect(registerResponse.status()).toBe(200);
    const { access_token } = await registerResponse.json();
    
    const syncResponse = await request.post(`${API_URL}/api/exchanges/coinbase/sync`, {
      headers: { Authorization: `Bearer ${access_token}` }
    });
    
    expect(syncResponse.status()).toBe(403);
  });
});

test.describe('Exchange UI Tests - Unlimited Users', () => {
  test('Exchange button visible for Unlimited users', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await loginAsPremiumUser(page);
    
    // Unlimited user should see Exchange button
    await expect(page.getByTestId('exchange-button')).toBeVisible();
  });

  test('Exchange modal opens and shows supported exchanges', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await loginAsPremiumUser(page);
    
    // Open Exchange modal
    await page.getByTestId('exchange-button').click();
    await expect(page.getByTestId('exchange-modal')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('exchange-modal-title')).toContainText('Exchange Integrations');
    
    // Wait for loading to finish
    await expect(page.getByTestId('exchange-loading')).not.toBeVisible({ timeout: 10000 });
    
    // Exchange cards should be visible
    await expect(page.getByTestId('exchange-cards')).toBeVisible();
    await expect(page.getByTestId('exchange-card-coinbase')).toBeVisible();
    await expect(page.getByTestId('exchange-card-binance')).toBeVisible();
    
    // Connect buttons should be visible
    await expect(page.getByTestId('connect-button-coinbase')).toBeVisible();
    await expect(page.getByTestId('connect-button-binance')).toBeVisible();
  });

  test('Click Connect Coinbase shows token input form', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await loginAsPremiumUser(page);
    
    await page.getByTestId('exchange-button').click();
    await expect(page.getByTestId('exchange-modal')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('exchange-loading')).not.toBeVisible({ timeout: 10000 });
    
    // Click Connect Coinbase
    await page.getByTestId('connect-button-coinbase').click();
    
    // Form should appear with token input
    await expect(page.getByTestId('connect-form-coinbase')).toBeVisible();
    await expect(page.getByTestId('coinbase-token-input')).toBeVisible();
    await expect(page.getByTestId('connect-submit-coinbase')).toBeVisible();
  });

  test('Click Connect Binance shows API key/secret form', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await loginAsPremiumUser(page);
    
    await page.getByTestId('exchange-button').click();
    await expect(page.getByTestId('exchange-modal')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('exchange-loading')).not.toBeVisible({ timeout: 10000 });
    
    // Click Connect Binance
    await page.getByTestId('connect-button-binance').click();
    
    // Form should appear with API key and secret inputs
    await expect(page.getByTestId('connect-form-binance')).toBeVisible();
    await expect(page.getByTestId('binance-api-key-input')).toBeVisible();
    await expect(page.getByTestId('binance-api-secret-input')).toBeVisible();
    await expect(page.getByTestId('connect-submit-binance')).toBeVisible();
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
