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
  await expect(page.getByTestId('auth-modal')).toBeVisible({ timeout: 5000 });
  await page.getByTestId('email-input').fill(TEST_EMAIL);
  await page.getByTestId('password-input').fill(TEST_PASSWORD);
  await page.getByTestId('auth-submit-button').click();
  await expect(page.getByTestId('user-info-bar')).toBeVisible({ timeout: 15000 });
}

async function analyzeWallet(page: Page, address: string) {
  await page.getByTestId('wallet-address-input').fill(address);
  await page.getByTestId('analyze-button').click();
  // Wait for analysis to complete - this can take a while
  await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 90000 });
}

test.describe('Core Tax Features', () => {
  
  test('Premium user login and wallet analysis with tax data', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    // Verify premium badge
    await expect(page.getByTestId('user-info-bar').getByText(/PREMIUM/i)).toBeVisible();
    
    // Analyze wallet
    await analyzeWallet(page, TEST_WALLET_ADDRESS);
    
    // Verify analysis results
    await expect(page.getByTestId('balance-card')).toBeVisible();
  });
  
  test('Tax Summary section displays after analysis', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    await analyzeWallet(page, TEST_WALLET_ADDRESS);
    
    // Scroll to Tax Summary section
    const taxSummary = page.getByText('Tax Summary').first();
    await taxSummary.scrollIntoViewIfNeeded();
    await expect(taxSummary).toBeVisible({ timeout: 10000 });
    
    // Check key metrics are visible (they're on the page)
    await expect(page.getByText(/Total Realized Gains/i).first()).toBeVisible();
    await expect(page.getByText(/Unrealized Gains/i).first()).toBeVisible();
    await expect(page.getByText(/FIFO/i).first()).toBeVisible();
  });
  
  test('Export Form 8949 buttons are visible', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    await analyzeWallet(page, TEST_WALLET_ADDRESS);
    
    // Scroll to export section
    const exportBtn = page.getByTestId('export-form-8949-btn');
    await exportBtn.scrollIntoViewIfNeeded();
    await expect(exportBtn).toBeVisible({ timeout: 10000 });
    
    // Check other export buttons
    await expect(page.getByRole('button', { name: /Short-term Only/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Long-term Only/i })).toBeVisible();
  });
});
