import asyncio

from polyprism.ingestion.clob_client import ClobClient
from polyprism.ingestion.gamma_client import GammaClient


async def main():
    print("Testing Gamma client...")
    gamma = GammaClient()
    markets = await gamma.fetch_active_markets(limit=5)
    print(f"  Fetched {len(markets)} markets")
    for m in markets[:2]:
        print(f"    - {m.condition_id[:16]}... | {m.question[:60]}")
        print(f"      Tokens: {len(m.tokens)}")

    if not markets:
        print("  No markets found — check GAMMA_API_URL in .env")
        return

    print("\nTesting CLOB client...")
    clob = ClobClient()
    # Use the first valid YES/NO token from the first market
    token_id = next(
        (t["token_id"] for m in markets for t in m.tokens if t["token_id"].isdigit()),
        None,
    )
    if token_id:
        book = await clob.fetch_order_book(token_id)
        print(f"  Fetched order book for token {token_id[:16]}...")
        print(f"    Bids: {len(book.bids)} levels, best: {book.best_bid}")
        print(f"    Asks: {len(book.asks)} levels, best: {book.best_ask}")
    else:
        print("  No valid token found in first market — skipping CLOB test")


if __name__ == "__main__":
    asyncio.run(main())
