import argparse
import json
from data.okx_client import OKXClient
from execution.executor import OKXExecutor

def main():
    parser = argparse.ArgumentParser(description="OKX account flow smoke check")
    parser.add_argument(
        "--submit-demo-order",
        action="store_true",
        help="Submit the configured demo buy with attached TP/SL (default: read-only)",
    )
    args = parser.parse_args()

    # 1. Config Yükleme
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    is_demo = config.get("execution", {}).get("is_demo", True)
    print(f"[MOD]: {'DEMO' if is_demo else 'LIVE'}")

    # 2. İstemcileri Başlatma (Guardrail olmadan)
    client = OKXClient(is_demo=is_demo)
    executor = OKXExecutor(is_demo=is_demo)

    # 3. GÖREV 1 TESTİ: Canlı Bakiye Sorgusu
    print("\n--- 1. GÖREV: Canlı Bakiye Sorgulanıyor ---")
    balances = client.get_balances()
    print(f"Bakiye Sonucu -> USDT: {balances.get('USDT')} | AVAX: {balances.get('AVAX')}")

    # Anlık Fiyat Kontrolü
    current_px = client.get_ticker_price("AVAX-USDT")
    print(f"Anlık AVAX Fiyatı: {current_px} USDT")

    # Order placement is opt-in to avoid trading during a routine check.
    if args.submit_demo_order and current_px > 0:
        print("\n--- 3. ve 4. GÖREV: Attached TP/SL Demo Emri ve Fill Teyidi Gönderiliyor ---")

        # %2.4 Take-Profit, %1.2 Stop-Loss hesaplama
        tp_price = round(current_px * 1.024, 2)
        sl_price = round(current_px * 0.988, 2)

        print(f"Emir Parametreleri -> Alış: Market | Miktar: 10 USDT | TP: {tp_price} | SL: {sl_price}")

        trade_result = executor.place_spot_buy(
            inst_id="AVAX-USDT",
            size=10.0,
            tp_trigger=tp_price,
            sl_trigger=sl_price
        )
        print("Borsa Yanıtı ve Fill Durumu:", trade_result)
    elif args.submit_demo_order:
        print("\n[UYARI] Fiyat 0 döndü, emir gönderilmedi.")
    else:
        print("\n[OKUMA MODU] Emir gönderilmedi. Demo emir için --submit-demo-order kullanın.")


if __name__ == "__main__":
    main()