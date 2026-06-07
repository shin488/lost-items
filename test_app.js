const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();

    page.on('console', msg => {
        console.log(`[${msg.type()}] ${msg.text()}`);
    });

    page.on('pageerror', err => {
        console.log(`[PAGE ERROR] ${err.message}`);
    });

    await page.goto('https://shin488.github.io/lost-items/', { 
        waitUntil: 'networkidle',
        timeout: 60000 
    });

    console.log('Page loaded, waiting for app init...');
    await page.waitForTimeout(45000);

    const splashVisible = await page.evaluate(() => {
        const s = document.getElementById('splash');
        return s ? 'SPLASH STILL VISIBLE' : 'SPLASH REMOVED (app started)';
    });
    console.log('Splash:', splashVisible);

    // Check for any error display in body
    const bodyHTML = await page.evaluate(() => document.body.innerHTML.substring(0, 500));
    console.log('Body HTML:', bodyHTML);

    await browser.close();
})();
