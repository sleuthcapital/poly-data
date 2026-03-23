# Plotting

Complete plotting recipes using poly-data with matplotlib. Copy-paste ready.

## Price History Line Chart

```python
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from poly_data import GammaClient, ClobClient, MarketFilter
from poly_data.markets import parse_json_field

# 1. Find an active H2H market
gamma = GammaClient()
clob = ClobClient()
events = gamma.fetch_events(active_only=True, sport_slugs=["nba"])

token_id = None
title = ""
for ev in events:
    for mkt in ev.get("markets", []):
        if MarketFilter.is_head_to_head(mkt):
            tokens = parse_json_field(
                mkt.get("clobTokenIds") or mkt.get("tokens", [])
            )
            if tokens:
                token_id = str(tokens[0])
                title = mkt["question"]
                break
    if token_id:
        break

# 2. Fetch & plot
df = clob.fetch_price_history_df(token_id)

fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df["timestamp"], df["price"], color="#3F51B5", linewidth=1.5)
ax.fill_between(df["timestamp"], df["price"], alpha=0.1, color="#3F51B5")
ax.axhline(y=0.5, color="gray", linestyle="--", alpha=0.5, label="50/50")

ax.set_ylim(0, 1)
ax.set_ylabel("Implied Probability")
ax.set_title(title, fontsize=13)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d %H:%M"))
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("price_line.png", dpi=150, bbox_inches="tight")
plt.show()
```

![Price line chart](../assets/price_line.png){ loading=lazy }

## Order Book Depth Chart

```python
import matplotlib.pyplot as plt
import numpy as np
from poly_data import ClobClient

clob = ClobClient()
book = clob.fetch_orderbook(token_id)

bids = book.get("bids", [])
asks = book.get("asks", [])

# Cumulative depth
bid_prices = [float(b["price"]) for b in sorted(bids, key=lambda x: -float(x["price"]))]
bid_cum = np.cumsum([float(b["size"]) for b in sorted(bids, key=lambda x: -float(x["price"]))])
ask_prices = [float(a["price"]) for a in sorted(asks, key=lambda x: float(x["price"]))]
ask_cum = np.cumsum([float(a["size"]) for a in sorted(asks, key=lambda x: float(a["price"]))])

fig, ax = plt.subplots(figsize=(10, 5))
ax.fill_between(bid_prices, bid_cum, alpha=0.4, color="#4CAF50", step="post", label="Bids")
ax.fill_between(ask_prices, ask_cum, alpha=0.4, color="#F44336", step="post", label="Asks")
ax.step(bid_prices, bid_cum, color="#4CAF50", linewidth=1.5, where="post")
ax.step(ask_prices, ask_cum, color="#F44336", linewidth=1.5, where="post")

ax.set_xlabel("Price")
ax.set_ylabel("Cumulative Size ($)")
ax.set_title("Order Book Depth")
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("depth_chart.png", dpi=150, bbox_inches="tight")
plt.show()
```

![Depth chart](../assets/depth_chart.png){ loading=lazy }

## Multi-Sport Event Distribution

```python
import matplotlib.pyplot as plt
from collections import Counter
from poly_data import GammaClient
from poly_data.markets import detect_sport

gamma = GammaClient()
events = gamma.fetch_events(active_only=True)

sports = Counter(
    detect_sport(ev.get("title", ""), tags=ev.get("tags"))
    for ev in events
)

# Horizontal bar chart
items = sports.most_common(12)
labels, counts = zip(*items)

fig, ax = plt.subplots(figsize=(10, 6))
colors = ["#3F51B5" if c > 50 else "#9FA8DA" for c in counts]
bars = ax.barh(labels, counts, color=colors)

for bar, count in zip(bars, counts):
    ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2,
            str(count), va="center", fontweight="bold", fontsize=10)

ax.set_xlabel("Number of Active Events", fontsize=11)
ax.set_title("Polymarket Sports Coverage", fontsize=14, fontweight="bold")
ax.invert_yaxis()
ax.grid(axis="x", alpha=0.3)

plt.tight_layout()
plt.savefig("sport_bars.png", dpi=150, bbox_inches="tight")
plt.show()
```

![Sport bars chart](../assets/sport_bars.png){ loading=lazy }

## H2H Market Share Pie Chart

```python
import matplotlib.pyplot as plt
from collections import Counter
from poly_data import GammaClient, MarketFilter
from poly_data.markets import detect_sport

gamma = GammaClient()
events = gamma.fetch_events(active_only=True)

h2h_sports = Counter()
for ev in events:
    sport = detect_sport(ev.get("title", ""), tags=ev.get("tags"))
    for mkt in ev.get("markets", []):
        if MarketFilter.is_head_to_head(mkt):
            h2h_sports[sport] += 1

top = h2h_sports.most_common(8)
labels, sizes = zip(*top)

fig, ax = plt.subplots(figsize=(8, 8))
explode = [0.05] * len(labels)
colors = plt.cm.Paired(range(len(labels)))

wedges, texts, autotexts = ax.pie(
    sizes, labels=labels, autopct="%1.1f%%",
    explode=explode, colors=colors,
    textprops={"fontsize": 11},
    pctdistance=0.82,
)
ax.set_title("H2H Markets by Sport", fontsize=14, fontweight="bold")

plt.tight_layout()
plt.savefig("h2h_pie.png", dpi=150, bbox_inches="tight")
plt.show()
```

![H2H pie chart](../assets/h2h_pie.png){ loading=lazy }

## Trade Volume Over Time

```python
import matplotlib.pyplot as plt
from poly_data import DataAPIClient

api = DataAPIClient()
df = api.fetch_trades_df(condition_id, max_offset=3000)

# Resample to hourly volume
df["hour"] = df["timestamp"].dt.floor("h")
hourly = df.groupby("hour")["size"].sum().reset_index()

fig, ax = plt.subplots(figsize=(12, 4))
ax.bar(hourly["hour"], hourly["size"], width=0.03, color="#FF7043", alpha=0.8)
ax.set_xlabel("Time")
ax.set_ylabel("Volume ($)")
ax.set_title("Hourly Trade Volume")
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig("trade_volume.png", dpi=150, bbox_inches="tight")
plt.show()
```

![Trade volume chart](../assets/trade_volume.png){ loading=lazy }
