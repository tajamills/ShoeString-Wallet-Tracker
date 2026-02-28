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

test.describe('Phase 3 Tax Enhancements', () => {
  
  test('Schedule D Export button is visible', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    await analyzeWallet(page, TEST_WALLET_ADDRESS);
    
    // Scroll to export section
    const scheduleDBtn = page.getByTestId('export-schedule-d-btn');
    await scheduleDBtn.scrollIntoViewIfNeeded();
    await expect(scheduleDBtn).toBeVisible({ timeout: 10000 });
  });

  test('Schedule D Export modal opens and has correct content', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    await analyzeWallet(page, TEST_WALLET_ADDRESS);
    
    // Click Schedule D button
    const scheduleDBtn = page.getByTestId('export-schedule-d-btn');
    await scheduleDBtn.scrollIntoViewIfNeeded();
    await scheduleDBtn.click();
    
    // Modal should open
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
    
    // Check modal content
    await expect(page.getByText(/Export Schedule D/i)).toBeVisible();
    await expect(page.getByText(/Tax Year/i)).toBeVisible();
    await expect(page.getByText(/Format/i)).toBeVisible();
    
    // Check export button
    await expect(page.getByRole('button', { name: /Export Schedule D/i })).toBeVisible();
    
    // Check cancel button
    await expect(page.getByRole('button', { name: /Cancel/i })).toBeVisible();
  });

  test('Schedule D Export modal has tax year selector', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    await analyzeWallet(page, TEST_WALLET_ADDRESS);
    
    // Open Schedule D modal
    const scheduleDBtn = page.getByTestId('export-schedule-d-btn');
    await scheduleDBtn.scrollIntoViewIfNeeded();
    await scheduleDBtn.click();
    
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
    
    // Click on tax year dropdown trigger
    const taxYearTrigger = page.locator('[role="dialog"]').locator('button').filter({ hasText: /20/ }).first();
    await expect(taxYearTrigger).toBeVisible();
  });

  test('Batch Categorize button is visible', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    await analyzeWallet(page, TEST_WALLET_ADDRESS);
    
    // Check batch categorize button
    const batchBtn = page.getByTestId('batch-categorize-btn');
    await batchBtn.scrollIntoViewIfNeeded();
    await expect(batchBtn).toBeVisible({ timeout: 10000 });
  });

  test('Batch Categorize modal opens and has correct content', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    await analyzeWallet(page, TEST_WALLET_ADDRESS);
    
    // Click batch categorize button
    const batchBtn = page.getByTestId('batch-categorize-btn');
    await batchBtn.scrollIntoViewIfNeeded();
    await batchBtn.click();
    
    // Modal should open
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
    
    // Check modal content
    await expect(page.getByText(/Batch Categorization/i)).toBeVisible();
    await expect(page.getByText(/Quick Action/i)).toBeVisible();
    await expect(page.getByText(/Custom Rules/i)).toBeVisible();
    
    // Check auto-categorize button
    await expect(page.getByRole('button', { name: /Auto-Categorize/i })).toBeVisible();
    
    // Check Apply Rules button
    await expect(page.getByRole('button', { name: /Apply Rules/i })).toBeVisible();
  });

  test('Batch Categorize modal has Add Rule button', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    await analyzeWallet(page, TEST_WALLET_ADDRESS);
    
    // Click batch categorize button
    const batchBtn = page.getByTestId('batch-categorize-btn');
    await batchBtn.scrollIntoViewIfNeeded();
    await batchBtn.click();
    
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
    
    // Check Add Rule button
    await expect(page.getByRole('button', { name: /Add Rule/i })).toBeVisible();
  });
});
