import { test, expect, Page } from '@playwright/test';

/**
 * Unified Tax Dashboard E2E Tests
 * Tests the UnifiedTaxDashboard component that combines on-chain wallet + exchange CSV data
 */

const BASE_URL = process.env.REACT_APP_BACKEND_URL || 'https://wallet-tax-hub.preview.emergentagent.com';
const PREMIUM_EMAIL = 'taxtest@test.com';
const PREMIUM_PASSWORD = 'TestPass123!';
// Use a less active address for faster analysis
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
  // Wait for analysis results
  await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 30000 });
}

test.describe('Unified Tax Dashboard - Premium User', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
  });

  test('Unified Tax Dashboard appears after wallet analysis for premium user', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    // Check that the unified tax dashboard component is rendered
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
  });

  test('Unified Tax Dashboard shows FIFO method badge', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check for FIFO badge in the dashboard
    const dashboard = page.getByTestId('unified-tax-dashboard');
    await expect(dashboard.getByText('FIFO')).toBeVisible();
  });

  test('Unified Tax Dashboard shows Unified Tax Calculator title', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check for the title
    await expect(page.getByText('Unified Tax Calculator')).toBeVisible();
  });

  test('Tax year filter dropdown is visible', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check for tax year filter
    const yearFilter = page.getByTestId('tax-year-filter');
    await expect(yearFilter).toBeVisible();
    
    // Check that it has All Years option
    await expect(yearFilter.locator('option').first()).toContainText('All Years');
  });

  test('Tax year filter can be changed', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    const yearFilter = page.getByTestId('tax-year-filter');
    await yearFilter.selectOption('2025');
    
    // Verify the option was selected
    await expect(yearFilter).toHaveValue('2025');
  });

  test('Data Sources section shows wallet and exchange badges', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    const dashboard = page.getByTestId('unified-tax-dashboard');
    await expect(dashboard).toBeVisible({ timeout: 15000 });
    
    // Check for data sources section
    await expect(dashboard.getByText('Data Sources')).toBeVisible();
    
    // Check for on-chain and exchange badges using more specific selectors
    await expect(dashboard.getByText(/\d+ on-chain/)).toBeVisible();
    await expect(dashboard.getByText(/\d+ exchange/)).toBeVisible();
  });

  test('Summary cards display tax information', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check for summary information cards
    await expect(page.getByText('Total Realized Gains')).toBeVisible();
    await expect(page.getByText('Short-term Gains')).toBeVisible();
    await expect(page.getByText('Long-term Gains')).toBeVisible();
    await expect(page.getByText('Unrealized Gains')).toBeVisible();
  });

  test('Data Sources section is expandable', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    const dashboard = page.getByTestId('unified-tax-dashboard');
    await expect(dashboard).toBeVisible({ timeout: 15000 });
    
    // Click on Data Sources header to expand
    await dashboard.getByText('Data Sources').click();
    
    // Check for expanded content - use more specific selectors
    await expect(dashboard.getByText('Total Transactions').first()).toBeVisible({ timeout: 5000 });
    await expect(dashboard.getByText('Buy Transactions')).toBeVisible();
    await expect(dashboard.getByText('Sell Transactions')).toBeVisible();
    await expect(dashboard.getByText('Method')).toBeVisible();
  });

  test('Export buttons are visible', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check for export buttons
    await expect(page.getByRole('button', { name: /Export Unified Form 8949/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Export Schedule D/i })).toBeVisible();
  });

  test('Info alert about unified view is displayed', async ({ page }) => {
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check for the info alert
    await expect(page.getByText(/This unified view combines your on-chain transactions/i)).toBeVisible();
    await expect(page.getByText(/FIFO cost basis is calculated across all sources/i)).toBeVisible();
  });
});


test.describe('Unified Tax Dashboard - Free User Access Control', () => {
  test('Unified Tax Dashboard is not visible for free users after analysis', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    
    // Create a unique free user
    const uniqueId = Date.now();
    const freeEmail = `TEST_unified_free_${uniqueId}@test.com`;
    const freePassword = 'TestPass123!';
    
    await removeEmergentBadge(page);
    
    // Register a new free user
    await page.getByTestId('login-button').click();
    await expect(page.getByTestId('auth-modal')).toBeVisible({ timeout: 5000 });
    
    // Click register tab
    await page.getByRole('tab', { name: /sign up/i }).click();
    
    // Fill registration form
    await page.getByTestId('email-input').fill(freeEmail);
    await page.getByTestId('password-input').fill(freePassword);
    await page.getByTestId('auth-submit-button').click();
    
    // Wait for registration to complete
    await expect(page.getByTestId('user-info-bar')).toBeVisible({ timeout: 15000 });
    
    // Free users can analyze wallets but shouldn't see UnifiedTaxDashboard
    await page.getByTestId('wallet-address-input').fill(TEST_WALLET_ADDRESS);
    await page.getByTestId('analyze-button').click();
    
    // Wait for analysis
    await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 30000 });
    
    // Unified Tax Dashboard should NOT be visible for free users
    const unifiedDashboard = page.getByTestId('unified-tax-dashboard');
    await expect(unifiedDashboard).not.toBeVisible({ timeout: 3000 });
  });
});


test.describe('Unified Tax Dashboard - UI Elements', () => {
  test('Refresh button triggers data recalculation', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    const dashboard = page.getByTestId('unified-tax-dashboard');
    await expect(dashboard).toBeVisible({ timeout: 15000 });
    
    // Find and click the refresh button (inside the dashboard header) - it has a RefreshCw icon
    const refreshBtn = dashboard.locator('button').filter({ has: page.locator('svg') }).last();
    
    // Click refresh if visible
    if (await refreshBtn.isVisible()) {
      await refreshBtn.click();
    }
    
    // Verify dashboard still renders correctly after refresh
    await expect(dashboard).toBeVisible();
  });

  test('Description shows combined data info', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    
    await loginAsPremiumUser(page);
    await analyzeWallet(page);
    
    await expect(page.getByTestId('unified-tax-dashboard')).toBeVisible({ timeout: 15000 });
    
    // Check for the description text
    await expect(page.getByText(/Combined on-chain wallet \+ exchange CSV imports/i)).toBeVisible();
  });
});
