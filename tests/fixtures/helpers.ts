import { Page, expect } from '@playwright/test';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'https://tax-analysis-phase2.preview.emergentagent.com';

export async function waitForAppReady(page: Page) {
  await page.waitForLoadState('domcontentloaded');
}

export async function dismissToasts(page: Page) {
  await page.addLocatorHandler(
    page.locator('[data-sonner-toast], .Toastify__toast, [role="status"].toast, .MuiSnackbar-root'),
    async () => {
      const close = page.locator('[data-sonner-toast] [data-close], [data-sonner-toast] button[aria-label="Close"], .Toastify__close-button, .MuiSnackbar-root button');
      await close.first().click({ timeout: 2000 }).catch(() => {});
    },
    { times: 10, noWaitAfter: true }
  );
}

export async function checkForErrors(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const errorElements = Array.from(
      document.querySelectorAll('.error, [class*="error"], [id*="error"]')
    );
    return errorElements.map(el => el.textContent || '').filter(Boolean);
  });
}

export async function loginAsTestUser(page: Page, email: string = 'taxtest@test.com', password: string = 'TestPass123!') {
  // Click the login button
  await page.getByTestId('login-button').click();
  
  // Wait for modal to appear
  await page.waitForSelector('[role="dialog"]');
  
  // Fill in login form
  await page.getByPlaceholder(/email/i).fill(email);
  await page.getByPlaceholder(/password/i).fill(password);
  
  // Submit login
  await page.locator('[role="dialog"]').getByRole('button', { name: /login/i }).click();
  
  // Wait for login to complete
  await expect(page.getByTestId('user-info-bar')).toBeVisible({ timeout: 10000 });
}

export async function getAuthToken(email: string = 'taxtest@test.com', password: string = 'TestPass123!'): Promise<string> {
  const response = await fetch(`${API_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  const data = await response.json();
  return data.access_token;
}

export async function analyzeWallet(page: Page, address: string) {
  // Enter wallet address
  await page.getByTestId('wallet-address-input').fill(address);
  
  // Click analyze button
  await page.getByTestId('analyze-button').click();
  
  // Wait for results to appear
  await expect(page.getByTestId('analysis-results')).toBeVisible({ timeout: 30000 });
}
