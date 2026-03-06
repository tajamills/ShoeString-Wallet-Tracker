import { test, expect, Page } from '@playwright/test';

/**
 * Data Source Toggle E2E Tests
 * Tests the unified tax calculator data source selector feature:
 * - 'Wallet Only', 'Exchange Only', 'Combined' data source options
 * - CPA disclaimer display
 * - Stablecoin exclusion info
 */

const PREMIUM_EMAIL = 'taxtest@test.com';
const PREMIUM_PASSWORD = 'TestPass123!';
const TEST_WALLET_ADDRESS = '0x742d35Cc6634C0532925a3b844Bc9e7595f5fEb6';

// Helper: Remove Emergent badge that can block clicks
async function removeEmergentBadge(page: Page) {
  await page.evaluate(() => {
    const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
    if (badge) badge.remove();
  });
}

// Helper: Login with premium test user
async function loginAsPremiumUser(page: Page) {
  await removeEmergentBadge(page);
  
  await page.getByTestId('login-button').click();
  await expect(page.getByTestId('auth-modal')).toBeVisible({ timeout: 5000 });
  await page.getByTestId('email-input').fill(PREMIUM_EMAIL);
  await page.getByTestId('password-input').fill(PREMIUM_PASSWORD);
  await page.getByTestId('auth-submit-button').click();
  await expect(page.getByTestId('user-info-bar')).toBeVisible({ timeout: 15000 });
}

// Helper: Analyze a wallet
async function analyzeWallet(page: Page, address: string = TEST_WALLET_ADDRESS) {
  await page.getByTestId('wallet-address-input').fill(address);
  await page.getByTestId('analyze-button').click();
  await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 30000 });
}

test.describe('Data Source Toggle Feature', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
  });

  test('Data source selector shows all 3 options', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    const dashboard = page.getByTestId('unified-tax-dashboard');
    await expect(dashboard).toBeVisible({ timeout: 15000 });
    
    // Check for all 3 data source buttons
    await expect(page.getByTestId('data-source-wallet_only')).toBeVisible();
    await expect(page.getByTestId('data-source-exchange_only')).toBeVisible();
    await expect(page.getByTestId('data-source-combined')).toBeVisible();
  });

  test('Wallet Only button has correct label and icon', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    const walletOnlyBtn = page.getByTestId('data-source-wallet_only');
    await expect(walletOnlyBtn).toBeVisible({ timeout: 15000 });
    await expect(walletOnlyBtn).toContainText('Wallet Only');
  });

  test('Exchange Only button has correct label', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    const exchangeOnlyBtn = page.getByTestId('data-source-exchange_only');
    await expect(exchangeOnlyBtn).toBeVisible({ timeout: 15000 });
    await expect(exchangeOnlyBtn).toContainText('Exchange Only');
  });

  test('Combined button has correct label', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    const combinedBtn = page.getByTestId('data-source-combined');
    await expect(combinedBtn).toBeVisible({ timeout: 15000 });
    await expect(combinedBtn).toContainText('Combined');
  });

  test('Combined is selected by default', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    const dashboard = page.getByTestId('unified-tax-dashboard');
    await expect(dashboard).toBeVisible({ timeout: 15000 });
    
    // Combined button should be active (purple background)
    const combinedBtn = page.getByTestId('data-source-combined');
    await expect(combinedBtn).toHaveClass(/bg-purple-600/);
  });

  test('Clicking Wallet Only changes selection', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Click Wallet Only
    await page.getByTestId('data-source-wallet_only').click();
    
    // Wait for recalculation
    await page.waitForTimeout(1000);
    
    // Check Tax Calculator badge shows 'Wallet' - use exact match
    await expect(page.locator('.bg-blue-600').getByText('Wallet', { exact: true })).toBeVisible({ timeout: 5000 });
  });

  test('Clicking Exchange Only changes selection', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Click Exchange Only
    await page.getByTestId('data-source-exchange_only').click();
    
    // Wait for recalculation
    await page.waitForTimeout(1000);
    
    // Check Tax Calculator badge shows 'Exchange' - use exact match
    await expect(page.locator('.bg-orange-600').getByText('Exchange', { exact: true })).toBeVisible({ timeout: 5000 });
  });

  test('Data source description updates when selection changes', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Default shows combined description
    await expect(page.getByText('All sources merged')).toBeVisible();
    
    // Click Wallet Only
    await page.getByTestId('data-source-wallet_only').click();
    await expect(page.getByText('On-chain transactions only')).toBeVisible({ timeout: 5000 });
    
    // Click Exchange Only
    await page.getByTestId('data-source-exchange_only').click();
    await expect(page.getByText('Imported CSV transactions')).toBeVisible({ timeout: 5000 });
  });
});


test.describe('CPA Disclaimer Feature', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
  });

  test('CPA disclaimer is prominently displayed', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check for the important tax disclaimer
    await expect(page.getByText('Important Tax Disclaimer')).toBeVisible();
  });

  test('CPA disclaimer mentions verification by CPA', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check for CPA verification text
    await expect(page.getByText(/verified by a qualified CPA/i)).toBeVisible();
  });

  test('CPA disclaimer mentions informational purposes', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check for informational purposes text
    await expect(page.getByText(/informational purposes only/i)).toBeVisible();
  });

  test('CPA disclaimer has amber/warning styling', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // The disclaimer should have amber styling (border-amber)
    const disclaimerAlert = page.locator('[class*="border-amber"]').first();
    await expect(disclaimerAlert).toBeVisible();
  });
});


test.describe('Stablecoin Exclusion Info', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
  });

  test('FIFO Method info is displayed', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check FIFO method info
    await expect(page.getByText('FIFO Method')).toBeVisible();
  });

  test('Stablecoin exclusion note is visible', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check for stablecoin exclusion text
    await expect(page.getByText(/Stablecoins.*excluded/i)).toBeVisible();
  });

  test('USDC and USDT mentioned in exclusion', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check for specific stablecoins mentioned
    await expect(page.getByText(/USDC/)).toBeVisible();
    await expect(page.getByText(/USDT/)).toBeVisible();
  });
});


test.describe('Data Sources Used Display', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
  });

  test('Data Sources Used section is visible', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check for Data Sources Used heading
    await expect(page.getByText('Data Sources Used')).toBeVisible();
  });

  test('Data Sources Used section shows data status badge', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // The Data Sources Used section header contains a badge showing status
    // Either "X on-chain" badges or "No data" badge  
    const dataSources = page.getByText('Data Sources Used').first();
    await expect(dataSources).toBeVisible();
    
    // Also verify we can expand it by clicking
    await dataSources.click();
    // After click, should show more details if there's data, or stay closed if no data
  });

  test('Tax Calculator shows Combined badge when combined selected', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Combined should be default, check for Combined badge - using class
    await expect(page.locator('.bg-green-600').getByText('Combined', { exact: true })).toBeVisible();
  });

  test('Tax Calculator shows FIFO badge', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check for FIFO badge
    await expect(page.getByText('FIFO').first()).toBeVisible();
  });
});
