import asyncio, os
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path(os.environ.get('ARCHON_SCREENSHOT_DIR', 'temp/browser/archon-branch'))
OUT.mkdir(parents=True, exist_ok=True)
BASE = os.environ.get('ARCHON_LOCAL_URL', 'http://localhost:5173')
if not BASE.startswith(('http://localhost:', 'http://127.0.0.1:')):
    raise ValueError('These financial demo tests must run against localhost only.')


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 1800})
        page = await context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.goto(BASE, wait_until='networkidle')
        await page.get_by_role('region', name='Supplier payouts table, scrollable').wait_for()
        await page.screenshot(path=str(OUT / 'desktop.png'))

        for name in [
            'Payouts',
            'Approvals',
            'Deposits',
            'Wallets & floors',
            'FX desk',
            'Completeness',
            'Receipts & audit',
            'Incidents',
            'Virtual cards',
            'Agent spending',
            'Invoice evaluator',
            'Integrations',
            'Command Center',
        ]:
            await page.get_by_role('button', name=name, exact=True).click()
            await page.get_by_role('heading', name=name, exact=True).wait_for()

        await page.get_by_role('button', name='Payouts', exact=True).click()
        eur = page.get_by_role('row').filter(has_text='obl-eur-1')

        # Test keyboard Escape in confirmation dialog cancels without mutating
        await eur.get_by_role('button', name='Approve', exact=True).click()
        await page.get_by_role('dialog', name='Confirm action').wait_for()
        await page.keyboard.press('Escape')
        await eur.get_by_text('NOT_APPROVED', exact=True).wait_for()

        # Approve EUR obligation
        await eur.get_by_role('button', name='Approve', exact=True).click()
        await page.get_by_role('button', name='Confirm', exact=True).click()
        await page.get_by_role('status').filter(has_text='Approve obl-eur-1:').wait_for()
        await eur.get_by_text('VALID', exact=True).wait_for()

        # Simulate EUR 500.00 deposit -> selectively invalidates obl-eur-1
        await page.get_by_role('button', name='Deposits', exact=True).click()
        await page.get_by_role('button', name='EUR 500.00', exact=True).click()
        await page.get_by_role('button', name='Confirm', exact=True).click()
        await page.get_by_role('status').filter(has_text='Simulate EUR 500.00 deposit:').wait_for()

        await page.get_by_role('button', name='Payouts', exact=True).click()
        await eur.get_by_text('INVALIDATED', exact=True).wait_for()
        assert await eur.get_by_role('button', name='Execute', exact=True).is_disabled()

        # Re-approve and execute EUR obligation
        await eur.get_by_role('button', name='Approve', exact=True).click()
        await page.get_by_role('button', name='Confirm', exact=True).click()
        await eur.get_by_text('VALID', exact=True).wait_for()
        await eur.get_by_role('button', name='Execute', exact=True).click()
        await page.get_by_role('button', name='Confirm', exact=True).click()
        await eur.get_by_text('PAID', exact=True).wait_for()

        # Receipts & audit view
        await page.get_by_role('button', name='Receipts & audit', exact=True).click()
        await page.locator('pre').wait_for()
        await page.screenshot(path=str(OUT / 'receipt.png'))

        # Wallets & floors: update reserve floor
        await page.get_by_role('button', name='Wallets & floors', exact=True).click()
        await page.get_by_role('button', name='Change reserve floor', exact=True).click()
        await page.get_by_role('button', name='Confirm', exact=True).click()
        await page.get_by_role('status').filter(has_text='Update EUR reserve floor').wait_for()

        # FX desk: lock FX quote and execute conversion
        await page.get_by_role('button', name='FX desk', exact=True).click()
        await page.get_by_role('button', name='Lock FX quote', exact=True).click()
        await page.get_by_role('button', name='Confirm', exact=True).click()
        await page.get_by_role('status').filter(has_text='Lock FX quote').wait_for()
        await page.get_by_role('button', name='Execute conversion', exact=True).click()
        await page.get_by_role('button', name='Confirm', exact=True).click()
        await page.get_by_role('status').filter(has_text='Execute FX conversion').wait_for()

        # Virtual cards
        await page.get_by_role('button', name='Virtual cards', exact=True).click()
        await page.get_by_role('button', name='Issue single-use card', exact=True).click()
        await page.get_by_role('button', name='Confirm', exact=True).click()
        await page.get_by_role('status').filter(has_text='Issue virtual card:').wait_for()
        await page.get_by_role('button', name='Test wrong MCC', exact=True).click()
        await page.get_by_role('button', name='Confirm', exact=True).click()
        await page.get_by_role('status').filter(has_text='Test wrong MCC 5812:').wait_for()
        print('Card rejection:', await page.get_by_role('status').inner_text())
        await page.get_by_role('button', name='Test authorization', exact=True).click()
        await page.get_by_role('button', name='Confirm', exact=True).click()
        await page.get_by_role('status').filter(has_text='Simulate card authorization:').wait_for()
        print('Card authorization:', await page.get_by_role('status').inner_text())

        # Invoice evaluator
        await page.get_by_role('button', name='Invoice evaluator', exact=True).click()
        await page.get_by_role('button', name='Inspect invoice', exact=True).click()
        await page.get_by_role('button', name='Confirm', exact=True).click()
        await page.get_by_role('status').filter(has_text='Inspect custom invoice:').wait_for()
        await page.locator('pre').wait_for()

        # Integrations & reconciliation verification
        await page.get_by_role('button', name='Integrations', exact=True).click()
        await page.get_by_role('button', name='Verify connection & reconcile', exact=True).click()
        await page.get_by_role('button', name='Confirm', exact=True).click()
        await page.get_by_role('status').filter(has_text='Verify provider integrations & reconcile:').wait_for()

        # Reload page and verify state durability across reload
        await page.reload(wait_until='networkidle')
        await page.get_by_role('button', name='Payouts', exact=True).click()
        await page.get_by_role('row').filter(has_text='obl-eur-1').get_by_text('PAID', exact=True).wait_for()

        await page.get_by_role('button', name='Command Center', exact=True).click()
        await page.set_viewport_size({'width': 390, 'height': 844})
        await page.screenshot(path=str(OUT / 'mobile.png'))
        assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        print(
            'Navigation, keyboard Escape dialog trap, EUR approval/deposit invalidation/reapproval/execution/receipt, reserve floor update, FX quote/conversion, card, invoice, integration reconciliation, and reload persistence flows passed. Errors:',
            errors,
        )
        assert not errors
        await browser.close()


asyncio.run(main())
