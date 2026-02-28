import { test, expect, Page } from '@playwright/test';

const TEST_EMAIL = 'taxtest@test.com';
const TEST_PASSWORD = 'TestPass123!';
const TEST_WALLET_ADDRESS = '0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045';

async function login(page: Page) {
  await page.evaluate(() => {
    const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
    if (badge) badge.remove();
  });
  
  await page.getByTestId('login-button').click();
  await page.waitForSelector('[role="dialog"]', { timeout: 5000 });
  await page.getByPlaceholder(/email/i).fill(TEST_EMAIL);
  await page.getByPlaceholder(/password/i).fill(TEST_PASSWORD);
  await page.locator('[role="dialog"]').getByRole('button', { name: /^login$/i }).click();
  await expect(page.getByTestId('user-info-bar')).toBeVisible({ timeout: 10000 });
}

test.describe('Transaction Categorizer', () => {
  
  test('Categorize button visible and opens modal', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    await page.getByTestId('wallet-address-input').fill(TEST_WALLET_ADDRESS);
    await page.getByTestId('analyze-button').click();
    await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 60000 });
    
    // Check categorize button
    const categorizeBtn = page.getByTestId('categorize-transactions-btn');
    await expect(categorizeBtn).toBeVisible();
    
    // Click and verify modal opens
    await categorizeBtn.click();
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/Category Guide/i)).toBeVisible();
  });
});
