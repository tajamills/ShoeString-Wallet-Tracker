import { test, expect, Page } from '@playwright/test';

const TEST_EMAIL = 'taxtest@test.com';
const TEST_PASSWORD = 'TestPass123!';
const TEST_WALLET_ADDRESS = '0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045';

async function login(page: Page) {
  // Remove Emergent badge
  await page.evaluate(() => {
    const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
    if (badge) badge.remove();
  });
  
  await page.getByTestId('login-button').click();
  
  // Wait for auth modal to appear
  await expect(page.getByTestId('auth-modal')).toBeVisible({ timeout: 5000 });
  
  // Use data-testid selectors for inputs
  await page.getByTestId('email-input').fill(TEST_EMAIL);
  await page.getByTestId('password-input').fill(TEST_PASSWORD);
  
  // Click submit button
  await page.getByTestId('auth-submit-button').click();
  
  // Wait for login success
  await expect(page.getByTestId('user-info-bar')).toBeVisible({ timeout: 15000 });
}

test.describe('Core Tax Features', () => {
  
  test('Premium user login and wallet analysis with tax data', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    // Verify premium badge
    await expect(page.getByTestId('user-info-bar').getByText(/PREMIUM/i)).toBeVisible();
    
    // Analyze wallet
    await page.getByTestId('wallet-address-input').fill(TEST_WALLET_ADDRESS);
    await page.getByTestId('analyze-button').click();
    await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 60000 });
    
    // Verify analysis results
    await expect(page.getByTestId('balance-card')).toBeVisible();
  });
  
  test('Tax Summary section displays after analysis', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    await page.getByTestId('wallet-address-input').fill(TEST_WALLET_ADDRESS);
    await page.getByTestId('analyze-button').click();
    await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 60000 });
    
    // Check Tax Summary heading
    await expect(page.getByRole('heading', { name: /tax summary/i })).toBeVisible({ timeout: 10000 });
    
    // Check key metrics
    await expect(page.getByText(/Total Realized Gains/i)).toBeVisible();
    await expect(page.getByText(/Unrealized Gains/i)).toBeVisible();
    await expect(page.getByText(/FIFO/i)).toBeVisible();
  });
  
  test('Export Form 8949 buttons are visible', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    await page.getByTestId('wallet-address-input').fill(TEST_WALLET_ADDRESS);
    await page.getByTestId('analyze-button').click();
    await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 60000 });
    
    // Check export buttons
    await expect(page.getByTestId('export-form-8949-btn')).toBeVisible();
    await expect(page.getByRole('button', { name: /Short-term Only/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Long-term Only/i })).toBeVisible();
  });
});
