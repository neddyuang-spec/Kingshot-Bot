# -*- coding: utf-8 -*-
import time
from playwright.sync_api import sync_playwright

PLAYERS = [
    {"name": "Light", "fid": "246147093", "kid": "1641"},
    {"name": "Pig", "fid": "264788350", "kid": "1641"},
    {"name": "Ogre", "fid": "279237769", "kid": "1641"},
    {"name": "MiniLight", "fid": "306868384", "kid": "1641"},
    {"name": "Hinoki", "fid": "265085587", "kid": "1641"},
    {"name": "Flora", "fid": "327944637", "kid": "1641"},
    {"name": "Handsome", "fid": "347892324", "kid": "628"},
]

REDEEM_PAGE_URL = "https://ks-giftcode.centurygame.com/"
CDK = "KS0810"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        for player in PLAYERS:
            print(f"正在為 [{player['kid']}服] {player['name']} (ID: {player['fid']}) 進行網頁兌換...")
            try:
                page.goto(REDEEM_PAGE_URL, timeout=30000)
                page.wait_for_selector("input", timeout=15000)

                inputs = page.locator("input")
                inputs.nth(0).fill(player['fid'])
                inputs.nth(1).fill(player['kid'])
                inputs.nth(2).fill(CDK)

                # 💡 改用更安全的方式點擊按鈕（嘗試點擊頁面上的按鈕或包含「兑换 / Confirm / 确认」的元素）
                # 這裡尋找頁面中的 button 或是有送出性質的點擊目標
                try:
                    # 先試著找常見的按鈕標籤
                    page.locator("button, .btn, [type='submit']").first.click()
                except:
                    # 如果找不到，改用模糊文字匹配（支援簡體或英文）
                    page.locator("text=/确认|兌換|Confirm|Redeem/i").first.click()

                time.sleep(2.5)
                body_text = page.inner_text("body")
                
                if "已領取" in body_text or "无法再次领取" in body_text or "重複領取" in body_text:
                    print("👉 結果：已經領取過該禮物")
                elif "成功" in body_text or "成功领取" in body_text or "信件" in body_text:
                    print("👉 結果：兌換成功！")
                else:
                    print("👉 結果：已送出指令")
                    
            except Exception as e:
                print(f"❌ 操作失敗: {e}")
            
            time.sleep(2)

        print("🎉 全部帳號執行完畢！")
        browser.close()

if __name__ == "__main__":
    main()
