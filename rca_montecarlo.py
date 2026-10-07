import random
import statistics as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

import rca_model as m

random.seed(1)
N = 20000
RS = [i / 20 for i in range(21)]

INK2 = "#52514e"
GRID = "#e4e3df"
S1 = "#2a78d6"
S2 = "#eb6834"


def draw():
    return {
        "d_na": random.uniform(0, 200),
        "d_cp": random.uniform(0, 200),
        "d_rca": random.uniform(0, 200),
        "d_lf": random.uniform(0, 200),
        "ec": random.uniform(0, 40),
        "crush": random.uniform(2.1, 8.8),
        "ef": random.uniform(0.75, 1.0),
    }


def co2(r, p, with_cement=True):
    ec = p["ec"] if with_cement else 0
    return m.co2_delta(r, p["d_na"], p["d_cp"], p["d_rca"], p["d_lf"], ec, p["crush"])[0]


def pct(xs, q):
    xs = sorted(xs)
    return xs[int(q * (len(xs) - 1))]


def simulate(samples, with_cement):
    rows = []
    for r in RS:
        mci = [m.mci_house(r, 1.0, p["ef"])[0] for p in samples]
        dco2 = [co2(r, p, with_cement) for p in samples]
        rows.append({
            "r": r,
            "mci": st.median(mci), "mci5": pct(mci, .05), "mci95": pct(mci, .95),
            "co2": st.median(dco2), "co25": pct(dco2, .05), "co295": pct(dco2, .95),
            "p_save": sum(x < 0 for x in dco2) / N,
        })
    return rows


def tornado(r=0.2):
    base = {"d_na": 50, "d_cp": 50, "d_rca": 50, "d_lf": 50, "ec": 0, "crush": 8.8}
    b0 = co2(r, base)
    params = [
        ("ec", 0, 40, "Extra cement 0-40 kg/m³ at r=100%"),
        ("d_rca", 0, 200, "RCA haul to ready-mix 0-200 km"),
        ("d_na", 0, 200, "Natural aggregate haul 0-200 km"),
        ("d_cp", 0, 200, "Haul to crushing plant 0-200 km"),
        ("d_lf", 0, 200, "Haul to landfill 0-200 km"),
        ("crush", 2.1, 8.8, "Crushing energy 2.1-8.8 MJ/t"),
    ]
    bars = [(label, co2(r, {**base, k: lo}) - b0, co2(r, {**base, k: hi}) - b0)
            for k, lo, hi, label in params]
    bars.sort(key=lambda t: max(abs(t[1]), abs(t[2])))
    return b0, bars


def style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 8,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2,
        "xtick.color": INK2, "ytick.color": INK2,
        "axes.spines.top": False, "axes.spines.right": False,
    })


def plot_tradeoff(no_cem, with_cem):
    fig, ax = plt.subplots(figsize=(6.3, 2.6), dpi=200)
    x = [100 * row["r"] for row in no_cem]
    ax.fill_between(x, [row["co25"] for row in no_cem], [row["co295"] for row in no_cem],
                    color=S1, alpha=0.15, linewidth=0, label="5-95% range, no extra cement")
    ax.plot(x, [row["co2"] for row in no_cem], color=S1, lw=2, label="Median, no extra cement")
    ax.plot(x, [row["co2"] for row in with_cem], color=S2, lw=2,
            label="Median, extra cement 0-40 kg/m³ (at r=100%)")
    ax.axhline(0, color=INK2, lw=0.8)
    ax.axvline(20, color=INK2, lw=0.8, ls=(0, (3, 3)))
    ax.text(21, ax.get_ylim()[0] * 0.92, "durability limit r = 20%", color=INK2, fontsize=7, va="bottom")
    ax.set_xlabel("Recycled share of coarse aggregate, r (%)")
    ax.set_ylabel("CO₂ change per house (kg CO₂e)")
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(0.22, 1.0))
    top = ax.secondary_xaxis("top", functions=(lambda v: v, lambda v: v))
    ticks = [0, 20, 50, 100]
    top.set_xticks(ticks)
    top.set_xticklabels([f"MCI {m.mci_house(t / 100)[0]:.3f}" for t in ticks], fontsize=7, color=INK2)
    top.spines["top"].set_color(GRID)
    fig.tight_layout()
    fig.savefig("fig1_tradeoff.png")
    plt.close(fig)


def plot_tornado(b0, bars):
    fig, ax = plt.subplots(figsize=(6.3, 2.0), dpi=200)
    for i, (_, low, high) in enumerate(bars):
        ax.barh(i, low, color=S1, height=0.6, edgecolor="white", linewidth=1)
        ax.barh(i, high, color=S2, height=0.6, edgecolor="white", linewidth=1)
    ax.set_yticks(range(len(bars)))
    ax.set_yticklabels([b[0] for b in bars])
    ax.axvline(0, color=INK2, lw=0.8)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_xlabel(f"Change from base case ({b0:+.0f} kg CO₂e per house), kg CO₂e")
    ax.legend(handles=[Patch(color=S1, label="Low end of range"),
                       Patch(color=S2, label="High end of range")],
              frameon=False, fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig("fig2_tornado.png")
    plt.close(fig)


if __name__ == "__main__":
    samples = [draw() for _ in range(N)]
    no_cem = simulate(samples, with_cement=False)
    with_cem = simulate(samples, with_cement=True)

    print("r   | MCI med [5-95]      | dCO2 no extra cement med [5-95], P(save) | with 0-40 kg cement med, P(save)")
    for a, b in zip(no_cem, with_cem):
        if a["r"] in (0.2, 0.5, 1.0):
            print(f"{a['r']:.0%} | {a['mci']:.3f} [{a['mci5']:.3f}-{a['mci95']:.3f}] | "
                  f"{a['co2']:+.0f} [{a['co25']:+.0f},{a['co295']:+.0f}] P={a['p_save']:.2f} | "
                  f"{b['co2']:+.0f} P={b['p_save']:.2f}")

    b0, bars = tornado()
    print(f"\nTornado base (r=20%, all hauls 50 km, no extra cement): {b0:+.0f} kgCO2e")
    for label, low, high in reversed(bars):
        print(f"  {label}: {low:+.0f} / {high:+.0f}")

    style()
    plot_tradeoff(no_cem, with_cem)
    plot_tornado(b0, bars)
    print("\nSaved fig1_tradeoff.png, fig2_tornado.png")
