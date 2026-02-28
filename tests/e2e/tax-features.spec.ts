import { test, expect, Page } from '@playwright/test';

const TEST_EMAIL = 'taxtest@test.com';
const TEST_PASSWORD = 'TestPass123!';
const TEST_WALLET_ADDRESS = '0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045';

async function login(page: Page) {
  // Remove Emergent badge if present
  await page.evaluate(() => {
    const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
    if (badge) badge.remove();
  });
  
  // Click login button
  await page.getByTestId('login-button').click();
  
  // Wait for auth modal
  await page.waitForSelector('[role="dialog"]', { timeout: 5000 });
  
  // Fill login form
  await page.getByPlaceholder(/email/i).fill(TEST_EMAIL);
  await page.getByPlaceholder(/password/i).fill(TEST_PASSWORD);
  
  // Click login button in modal
  await page.locator('[role="dialog"]').getByRole('button', { name: /^login$/i }).click();
  
  // Wait for login success
  await expect(page.getByTestId('user-info-bar')).toBeVisible({ timeout: 10000 });
}

test.describe('Tax Features - Core Flows', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
  });
  
  test('Premium user sees PREMIUM badge after login', async ({ page }) => {
    await login(page);
    
    // Check user info shows premium tier
    const userInfoBar = page.getByTestId('user-info-bar');
    await expect(userInfoBar).toBeVisible();
    await expect(userInfoBar.getByText(/PREMIUM/i)).toBeVisible();
  });
  
  test('Premium user can analyze wallet', async ({ page }) => {
    await login(page);
    
    // Enter wallet address
    await page.getByTestId('wallet-address-input').fill(TEST_WALLET_ADDRESS);
    
    // Click analyze
    await page.getByTestId('analyze-button').click();
    
    // Wait for results (API can be slow)
    await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 60000 });
    
    // Verify key elements are visible
    await expect(page.getByTestId('received-card')).toBeVisible();
    await expect(page.getByTestId('sent-card')).toBeVisible();
    await expect(page.getByTestId('balance-card')).toBeVisible();
  });
});

test.describe('Tax Dashboard UI', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
  });
  
  test('Tax Summary displays after wallet analysis', async ({ page }) => {
    // Analyze wallet
    await page.getByTestId('wallet-address-input').fill(TEST_WALLET_ADDRESS);
    await page.getByTestId('analyze-button').click();
    
    // Wait for analysis
    await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 60000 });
    
    // Look for Tax Summary section
    // Note: Tax Dashboard only shows if tax_data exists
    const taxSummaryHeading = page.getByRole('heading', { name: /tax summary/i });
    await expect(taxSummaryHeading).toBeVisible({ timeout: 10000 });
  });
  
  test('Tax Summary shows key metrics', async ({ page }) => {
    // Analyze wallet
    await page.getByTestId('wallet-address-input').fill(TEST_WALLET_ADDRESS);
    await page.getByTestId('analyze-button').click();
    await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 60000 });
    
    // Check for Tax Summary content
    // Look for key metrics text
    await expect(page.getByText(/Total Realized Gains/i)).toBeVisible();
    await expect(page.getByText(/Unrealized Gains/i)).toBeVisible();
    await expect(page.getByText(/Total Cost Basis/i)).toBeVisible();
    
    // Check for FIFO method badge
    await expect(page.getByText(/FIFO/i)).toBeVisible();
  });
  
  test('Tax Summary shows gains by holding period', async ({ page }) => {
    // Analyze wallet
    await page.getByTestId('wallet-address-input').fill(TEST_WALLET_ADDRESS);
    await page.getByTestId('analyze-button').click();
    await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 60000 });
    
    // Check for holding period breakdown
    await expect(page.getByText(/Short-term/i)).toBeVisible();
    await expect(page.getByText(/Long-term/i)).toBeVisible();
  });
  
  test('Export Form 8949 button is visible', async ({ page }) => {
    // Analyze wallet
    await page.getByTestId('wallet-address-input').fill(TEST_WALLET_ADDRESS);
    await page.getByTestId('analyze-button').click();
    await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 60000 });
    
    // Check for Export Form 8949 button
    const exportBtn = page.getByTestId('export-form-8949-btn');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toHaveText(/Export Form 8949/i);
  });
  
  test('Export Tax Forms section has all filter buttons', async ({ page }) => {
    // Analyze wallet
    await page.getByTestId('wallet-address-input').fill(TEST_WALLET_ADDRESS);
    await page.getByTestId('analyze-button').click();
    await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 60000 });
    
    // Check for export buttons
    await expect(page.getByRole('button', { name: /Export Form 8949 \(All\)/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Short-term Only/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Long-term Only/i })).toBeVisible();
  });
});

test.describe('TaxDashboard Expandable Sections', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    // Analyze wallet
    await page.getByTestId('wallet-address-input').fill(TEST_WALLET_ADDRESS);
    await page.getByTestId('analyze-button').click();
    await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 60000 });
  });
  
  test('Unrealized Gains section is expandable', async ({ page }) => {
    // Find unrealized gains section header (it should contain chevron for collapse/expand)
    const unrealizedSection = page.getByRole('heading', { name: /Unrealized Gains/i }).locator('..');
    await expect(unrealizedSection).toBeVisible();
    
    // Click to expand
    await unrealizedSection.click();
    
    // After click, table should be visible
    // Look for table headers that indicate unrealized gains details
    await expect(page.getByText(/Acquisition Date/i).or(page.getByText(/Buy Date/i))).toBeVisible({ timeout: 5000 });
  });
  
  test('Tax Lots section is expandable if present', async ({ page }) => {
    // Look for Tax Lots section
    const taxLotsHeading = page.getByRole('heading', { name: /Tax Lots/i });
    
    // If exists, try expanding
    if (await taxLotsHeading.isVisible()) {
      const taxLotsSection = taxLotsHeading.locator('..');
      await taxLotsSection.click();
      
      // Should show details after expanding
      await expect(page.getByText(/Date Acquired/i)).toBeVisible({ timeout: 5000 });
    } else {
      // Tax Lots section might not exist if no lots
      test.skip();
    }
  });
});

test.describe('Transaction Categorizer', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page);
    
    // Analyze wallet
    await page.getByTestId('wallet-address-input').fill(TEST_WALLET_ADDRESS);
    await page.getByTestId('analyze-button').click();
    await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 60000 });
  });
  
  test('Categorize Transactions button is visible for premium users', async ({ page }) => {
    // Look for categorize button
    const categorizeBtn = page.getByTestId('categorize-transactions-btn');
    await expect(categorizeBtn).toBeVisible();
    await expect(categorizeBtn).toHaveText(/Categorize Transactions/i);
  });
  
  test('Clicking categorize button opens modal', async ({ page }) => {
    // Click categorize button
    await page.getByTestId('categorize-transactions-btn').click();
    
    // Modal should appear
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/Categorize Transactions/i)).toBeVisible();
    
    // Should show category options
    await expect(page.getByText(/Category Guide/i)).toBeVisible();
  });
  
  test('Transaction categorizer shows category options', async ({ page }) => {
    // Open categorizer
    await page.getByTestId('categorize-transactions-btn').click();
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
    
    // Check for category types in the guide
    await expect(page.getByText(/Trade/i)).toBeVisible();
    await expect(page.getByText(/Income/i)).toBeVisible();
    await expect(page.getByText(/Gift/i)).toBeVisible();
    await expect(page.getByText(/Transfer/i)).toBeVisible();
  });
});
