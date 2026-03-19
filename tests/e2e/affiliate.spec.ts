import { test, expect } from '@playwright/test';

const BASE_URL = process.env.REACT_APP_BACKEND_URL || 'https://crypto-bag-tracker.preview.emergentagent.com';

// Helper function to register a new user and accept terms
async function registerAndLogin(page, email: string, password: string = 'TestPass123!') {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: /login/i }).click();
  await expect(page.locator('[role="dialog"]')).toBeVisible();
  
  await page.getByPlaceholder('you@example.com').fill(email);
  await page.getByPlaceholder('••••••••').fill(password);
  await page.getByText("Don't have an account? Sign up").click();
  await page.waitForTimeout(300);
  await page.getByPlaceholder('you@example.com').fill(email);
  await page.getByPlaceholder('••••••••').fill(password);
  await page.locator('[role="dialog"]').getByRole('button', { name: /sign up/i }).click();
  
  // Handle terms modal
  await expect(page.getByRole('heading', { name: 'Terms of Service', exact: true })).toBeVisible({ timeout: 10000 });
  const scrollViewport = page.locator('[data-radix-scroll-area-viewport]');
  await scrollViewport.evaluate(el => el.scrollTo(0, el.scrollHeight));
  await page.waitForTimeout(500);
  await page.getByTestId('terms-checkbox').click({ force: true });
  await expect(page.getByTestId('accept-terms-btn')).toBeEnabled({ timeout: 3000 });
  await page.getByTestId('accept-terms-btn').click();
  
  await expect(page.getByText(email)).toBeVisible({ timeout: 10000 });
}

test.describe('Affiliate Program - Basic Tests', () => {
  test('Homepage loads with Login button', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('button', { name: /login/i })).toBeVisible();
    await expect(page.getByText('Crypto Bag Tracker')).toBeVisible();
  });

  test('Affiliate button visible when logged in', async ({ page }) => {
    const email = `TEST_affbtn_${Date.now()}@test.com`;
    await registerAndLogin(page, email);
    await expect(page.getByTestId('affiliate-button')).toBeVisible();
  });

  test('Affiliate modal opens with registration form', async ({ page }) => {
    const email = `TEST_affmodal_${Date.now()}@test.com`;
    await registerAndLogin(page, email);
    
    await page.getByTestId('affiliate-button').click();
    await expect(page.getByTestId('affiliate-modal')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('affiliate-registration-form')).toBeVisible();
    await expect(page.getByTestId('affiliate-code-input')).toBeVisible();
    await expect(page.getByTestId('affiliate-name-input')).toBeVisible();
    await expect(page.getByTestId('affiliate-register-button')).toBeVisible();
  });

  test('Affiliate registration form validation', async ({ page }) => {
    const email = `TEST_affval_${Date.now()}@test.com`;
    await registerAndLogin(page, email);
    
    await page.getByTestId('affiliate-button').click();
    await expect(page.getByTestId('affiliate-modal')).toBeVisible({ timeout: 5000 });
    
    // Register button should be disabled without required fields
    const registerBtn = page.getByTestId('affiliate-register-button');
    await expect(registerBtn).toBeDisabled();
    
    // Fill only code, button still disabled
    await page.getByTestId('affiliate-code-input').fill('TESTCODE');
    await expect(registerBtn).toBeDisabled();
    
    // Fill name, button should be enabled
    await page.getByTestId('affiliate-name-input').fill('Test User');
    await expect(registerBtn).toBeEnabled();
  });
});

test.describe('Affiliate Registration', () => {
  test('User can register as affiliate', async ({ page }) => {
    const timestamp = Date.now();
    const email = `TEST_affreg_${timestamp}@test.com`;
    const affiliateCode = `T${timestamp.toString().slice(-7)}`;
    
    await registerAndLogin(page, email);
    
    await page.getByTestId('affiliate-button').click();
    await expect(page.getByTestId('affiliate-modal')).toBeVisible({ timeout: 5000 });
    
    // Fill registration form
    await page.getByTestId('affiliate-code-input').fill(affiliateCode);
    await page.getByTestId('affiliate-name-input').fill('Test Affiliate');
    await page.getByTestId('affiliate-paypal-input').fill('test@paypal.com');
    
    // Submit
    await page.getByTestId('affiliate-register-button').click();
    
    // Should show dashboard with code
    await expect(page.getByTestId('affiliate-dashboard')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('affiliate-code-badge')).toHaveText(affiliateCode.toUpperCase());
  });
});

test.describe('Upgrade Modal - Affiliate Code', () => {
  test('Upgrade modal has affiliate code input', async ({ page }) => {
    const email = `TEST_upgmod_${Date.now()}@test.com`;
    await registerAndLogin(page, email);
    
    await page.getByTestId('upgrade-button').click();
    await expect(page.getByTestId('upgrade-modal')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('upgrade-affiliate-code-input')).toBeVisible();
    await expect(page.getByText(/referral code/i)).toBeVisible();
  });

  test('Invalid affiliate code shows error', async ({ page }) => {
    const email = `TEST_invcode_${Date.now()}@test.com`;
    await registerAndLogin(page, email);
    
    await page.getByTestId('upgrade-button').click();
    await expect(page.getByTestId('upgrade-modal')).toBeVisible({ timeout: 5000 });
    
    // Enter invalid code
    await page.getByTestId('upgrade-affiliate-code-input').fill('INVALIDCODE999');
    
    // Wait for validation
    await expect(page.getByTestId('affiliate-validation-status')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('affiliate-validation-status')).toHaveClass(/text-red/);
  });

  test('Valid affiliate code shows discount', async ({ page }) => {
    // First create an affiliate
    const timestamp = Date.now();
    const affiliateEmail = `TEST_vaff_${timestamp}@test.com`;
    const affiliateCode = `V${timestamp.toString().slice(-7)}`;
    
    // Register affiliate via API
    const regRes = await page.request.post(`${BASE_URL}/api/auth/register`, {
      data: { email: affiliateEmail, password: 'TestPass123!' }
    });
    
    if (regRes.ok()) {
      const regData = await regRes.json();
      await page.request.post(`${BASE_URL}/api/affiliate/register`, {
        headers: { Authorization: `Bearer ${regData.access_token}` },
        data: { affiliate_code: affiliateCode, name: 'Test Affiliate' }
      });
    }
    
    // Now register a different user
    const userEmail = `TEST_vuser_${timestamp}@test.com`;
    await registerAndLogin(page, userEmail);
    
    await page.getByTestId('upgrade-button').click();
    await expect(page.getByTestId('upgrade-modal')).toBeVisible({ timeout: 5000 });
    
    // Enter valid code
    await page.getByTestId('upgrade-affiliate-code-input').fill(affiliateCode);
    
    // Wait for validation
    await expect(page.getByTestId('affiliate-validation-status')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('affiliate-validation-status')).toHaveClass(/text-green/);
    await expect(page.getByTestId('affiliate-validation-status')).toContainText(/\$10 off/i);
    
    // Check discounted price is shown
    await expect(page.getByText('$90.88/year').first()).toBeVisible();
  });
});
