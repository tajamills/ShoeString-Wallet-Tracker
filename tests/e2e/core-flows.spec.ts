import { test, expect, Page } from '@playwright/test';

/**
 * Core Flows E2E Tests
 * Tests core user journeys after App.js refactoring with useAnalysis and usePayment hooks
 */

const BASE_URL = process.env.REACT_APP_BACKEND_URL || 'https://chain-custody-tool.preview.emergentagent.com';
const TEST_EMAIL = 'coretest@test.com';
const TEST_PASSWORD = 'TestPass123!';
const TEST_WALLET_ADDRESS = '0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045'; // Vitalik's wallet

// Helper: Remove Emergent badge that can block clicks
async function removeEmergentBadge(page: Page) {
  await page.evaluate(() => {
    const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
    if (badge) badge.remove();
  });
}

// Helper: Login with test user
async function login(page: Page, email: string = TEST_EMAIL, password: string = TEST_PASSWORD) {
  await removeEmergentBadge(page);
  
  await page.getByTestId('login-button').click();
  await expect(page.getByTestId('auth-modal')).toBeVisible({ timeout: 5000 });
  await page.getByTestId('email-input').fill(email);
  await page.getByTestId('password-input').fill(password);
  await page.getByTestId('auth-submit-button').click();
  await expect(page.getByTestId('user-info-bar')).toBeVisible({ timeout: 15000 });
}

test.describe('Homepage and Login', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
  });

  test('Homepage loads correctly', async ({ page }) => {
    // Check main title
    await expect(page.getByText('Crypto Bag Tracker')).toBeVisible();
    
    // Check login prompt for unauthenticated users
    await expect(page.getByTestId('login-prompt')).toBeVisible();
    await expect(page.getByTestId('login-button')).toBeVisible();
    
    // Check wallet input card
    await expect(page.getByTestId('wallet-input-card')).toBeVisible();
    await expect(page.getByTestId('wallet-address-input')).toBeVisible();
    
    // Analyze button should be disabled for unauthenticated users
    await expect(page.getByTestId('analyze-button')).toBeDisabled();
  });

  test('Login modal opens and has required fields', async ({ page }) => {
    await removeEmergentBadge(page);
    
    await page.getByTestId('login-button').click();
    await expect(page.getByTestId('auth-modal')).toBeVisible({ timeout: 5000 });
    
    // Check form fields exist
    await expect(page.getByTestId('email-input')).toBeVisible();
    await expect(page.getByTestId('password-input')).toBeVisible();
    await expect(page.getByTestId('auth-submit-button')).toBeVisible();
    
    // Check sign up link exists
    await expect(page.getByText(/Don't have an account/i)).toBeVisible();
  });

  test('User can register new account', async ({ page }) => {
    await removeEmergentBadge(page);
    
    const uniqueEmail = `test_${Date.now()}@test.com`;
    
    await page.getByTestId('login-button').click();
    await expect(page.getByTestId('auth-modal')).toBeVisible({ timeout: 5000 });
    
    // Switch to signup mode
    await page.getByText(/Don't have an account/i).click();
    
    // Fill registration form
    await page.getByTestId('email-input').fill(uniqueEmail);
    await page.getByTestId('password-input').fill(TEST_PASSWORD);
    await page.getByTestId('auth-submit-button').click();
    
    // Should show terms modal or user-info-bar
    await expect(page.getByTestId('user-info-bar').or(page.getByTestId('terms-modal'))).toBeVisible({ timeout: 15000 });
  });

  test('Login with existing user', async ({ page }) => {
    await login(page, 'taxtest@test.com', TEST_PASSWORD);
    
    // Verify user info bar is visible
    await expect(page.getByTestId('user-info-bar')).toBeVisible();
    
    // Verify user email is shown
    await expect(page.getByText('taxtest@test.com')).toBeVisible();
    
    // Verify logout button exists
    await expect(page.getByTestId('logout-button')).toBeVisible();
  });

  test('User can logout', async ({ page }) => {
    await login(page, 'taxtest@test.com', TEST_PASSWORD);
    
    // Verify logged in
    await expect(page.getByTestId('user-info-bar')).toBeVisible();
    
    // Click logout
    await removeEmergentBadge(page);
    await page.getByTestId('logout-button').click();
    
    // Verify logged out - login prompt should appear
    await expect(page.getByTestId('login-prompt')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('login-button')).toBeVisible();
  });
});

test.describe('Wallet Analysis - useAnalysis Hook', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page, 'taxtest@test.com', TEST_PASSWORD);
  });

  test('Can enter wallet address and analyze', async ({ page }) => {
    // Fill wallet address
    await page.getByTestId('wallet-address-input').fill(TEST_WALLET_ADDRESS);
    
    // Click analyze
    await page.getByTestId('analyze-button').click();
    
    // Wait for analysis results (can take time for API call)
    await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 90000 });
    
    // Verify key cards are displayed
    await expect(page.getByTestId('received-card')).toBeVisible();
    await expect(page.getByTestId('sent-card')).toBeVisible();
    await expect(page.getByTestId('balance-card')).toBeVisible();
  });

  test('Invalid wallet address shows error', async ({ page }) => {
    // Try invalid address
    await page.getByTestId('wallet-address-input').fill('invalid-address');
    await page.getByTestId('analyze-button').click();
    
    // Should show error
    await expect(page.getByTestId('error-alert')).toBeVisible({ timeout: 5000 });
  });

  test('Chain selector shows available chains', async ({ page }) => {
    // Check chain selector exists
    const chainSelector = page.locator('select');
    await expect(chainSelector).toBeVisible();
    
    // Should have Ethereum selected by default
    await expect(chainSelector).toHaveValue('ethereum');
    
    // Premium user should be able to select other chains
    // (taxtest@test.com is a premium user)
  });
});

test.describe('User Interface Components', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page, 'taxtest@test.com', TEST_PASSWORD);
  });

  test('Affiliate button is visible and opens modal', async ({ page }) => {
    await removeEmergentBadge(page);
    
    await expect(page.getByTestId('affiliate-button')).toBeVisible();
    await page.getByTestId('affiliate-button').click();
    
    await expect(page.getByTestId('affiliate-modal')).toBeVisible({ timeout: 5000 });
  });

  test('Saved Wallets toggle works', async ({ page }) => {
    // Find the saved wallets button
    const savedWalletsButton = page.getByRole('button', { name: /Show Saved Wallets/i });
    await expect(savedWalletsButton).toBeVisible();
    
    // Click to show
    await savedWalletsButton.click();
    
    // Should show saved wallets section (even if empty)
    // The button text should change to "Hide Saved Wallets"
    await expect(page.getByRole('button', { name: /Hide Saved Wallets/i })).toBeVisible();
  });

  test('Date filter inputs are available', async ({ page }) => {
    await expect(page.getByTestId('start-date-input')).toBeVisible();
    await expect(page.getByTestId('end-date-input')).toBeVisible();
  });
});

test.describe('Subscription Features', () => {
  test('Free user sees upgrade button', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    
    // Create a unique free user for this test
    const uniqueEmail = `freeuser_${Date.now()}@test.com`;
    
    await removeEmergentBadge(page);
    await page.getByTestId('login-button').click();
    await expect(page.getByTestId('auth-modal')).toBeVisible({ timeout: 5000 });
    
    // Switch to signup mode
    await page.getByText(/Don't have an account/i).click();
    await page.getByTestId('email-input').fill(uniqueEmail);
    await page.getByTestId('password-input').fill(TEST_PASSWORD);
    await page.getByTestId('auth-submit-button').click();
    
    // Wait for login
    await expect(page.getByTestId('user-info-bar')).toBeVisible({ timeout: 15000 });
    
    // Free user should see upgrade button
    await expect(page.getByTestId('upgrade-button')).toBeVisible();
    
    // Free user should see FREE badge
    await expect(page.getByText('FREE', { exact: true })).toBeVisible();
  });

  test('Premium user sees Exchanges button', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await login(page, 'taxtest@test.com', TEST_PASSWORD);
    
    // Premium user should see Exchanges button instead of Upgrade button
    await expect(page.getByTestId('exchange-button')).toBeVisible();
  });

  test('Upgrade modal opens', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    
    const uniqueEmail = `upgradetest_${Date.now()}@test.com`;
    
    await removeEmergentBadge(page);
    await page.getByTestId('login-button').click();
    await expect(page.getByTestId('auth-modal')).toBeVisible({ timeout: 5000 });
    
    // Switch to signup
    await page.getByText(/Don't have an account/i).click();
    await page.getByTestId('email-input').fill(uniqueEmail);
    await page.getByTestId('password-input').fill(TEST_PASSWORD);
    await page.getByTestId('auth-submit-button').click();
    
    await expect(page.getByTestId('user-info-bar')).toBeVisible({ timeout: 15000 });
    
    // If terms modal appears, scroll and accept it
    const termsTitle = page.getByText('Terms of Service').first();
    if (await termsTitle.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Scroll the terms content to bottom to enable checkbox
      const scrollArea = page.locator('[data-radix-scroll-area-viewport]');
      await scrollArea.evaluate(el => el.scrollTop = el.scrollHeight);
      await page.waitForTimeout(500);
      
      // Now click the checkbox
      await page.locator('[data-state="unchecked"]').click({ force: true });
      
      // Click accept button
      await page.getByRole('button', { name: /accept/i }).click({ force: true });
      await page.waitForTimeout(500);
    }
    
    // Click upgrade button
    await page.getByTestId('upgrade-button').click({ force: true });
    
    // Upgrade modal should open
    await expect(page.getByTestId('upgrade-modal')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Terms of Service', () => {
  test('New user sees terms modal', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    
    const uniqueEmail = `tostest_${Date.now()}@test.com`;
    
    await removeEmergentBadge(page);
    await page.getByTestId('login-button').click();
    await expect(page.getByTestId('auth-modal')).toBeVisible({ timeout: 5000 });
    
    // Switch to signup
    await page.getByText(/Don't have an account/i).click();
    await page.getByTestId('email-input').fill(uniqueEmail);
    await page.getByTestId('password-input').fill(TEST_PASSWORD);
    await page.getByTestId('auth-submit-button').click();
    
    // New user should see terms modal
    await expect(page.getByTestId('terms-modal').or(page.getByText(/Terms of Service/i).first())).toBeVisible({ timeout: 15000 });
  });
});
