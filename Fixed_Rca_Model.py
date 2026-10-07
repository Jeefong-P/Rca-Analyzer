HOUSE = {
    "concrete": 129226,
    "block": 14560,
    "steel": 9626,
    "tile": 5129,
    "glass": 462,
    "gypsum": 109,
    "wood": 84,
    "al": 74,
}
M_HOUSE = sum(HOUSE.values())

EOL = {
    "concrete": ("R", 1.0),
    "block": ("R", 1.0),
    "steel": ("R", 1.0),
    "tile": ("U", 1.0),
    "glass": ("U", 1.0),
    "al": ("U", 1.0),
    "gypsum": ("L", 0.0),
    "wood": ("L", 0.0),
}

MIX = {"cement": 380, "coarse": 1006, "sand": 800, "water": 191}
RHO_C = sum(MIX.values())
V_CONC = HOUSE["concrete"] / RHO_C

SG_NA, SG_RCA = 2.67, 2.45
ABS_NA, ABS_RCA = 0.0046, 0.0561
YIELD_COARSE = 0.75

EF_CEMENT = 0.788
EF_LIMESTONE = 0.0025
EF_TRUCK_FULL = 0.0489
EF_TRUCK_EMPTY = 0.6053
PAYLOAD = 16.0
EF_ELEC = 0.5562
CRUSH_MJ_PER_T = 8.8

EF_TRUCK_RT = EF_TRUCK_FULL + EF_TRUCK_EMPTY / PAYLOAD


def crush_ef(mj_per_t=CRUSH_MJ_PER_T):
    return mj_per_t / 3.6 * EF_ELEC


def rca_mass(r):
    return r * MIX["coarse"] * (SG_RCA / SG_NA) * V_CONC


def mci_house(r, X=1.0, E_F=YIELD_COARSE, C_R_conc=1.0, E_C=1.0):
    m_rca = rca_mass(r)
    V = W = dW = 0.0
    for name, m in HOUSE.items():
        route, frac = EOL[name]
        FR = m_rca / m if name == "concrete" else 0.0
        CR = C_R_conc if name == "concrete" else (frac if route == "R" else 0.0)
        CU = frac if route == "U" else 0.0
        w0 = m * (1 - CR - CU)
        wc = m * (1 - E_C) * CR
        wf = m * (1 - E_F) * FR / E_F
        V += m * (1 - FR)
        W += w0 + (wf + wc) / 2
        dW += (wf - wc) / 2
    LFI = (V + W) / (2 * M_HOUSE + dW)
    return max(0.0, 1 - LFI * 0.9 / X), LFI, m_rca


def co2_delta(r, d_na, d_cp, d_rca, d_lf, extra_cement=0.0, crush_mj=CRUSH_MJ_PER_T):
    m_rca_t = rca_mass(r) / 1000
    m_in_t = m_rca_t / YIELD_COARSE
    m_na_t = r * MIX["coarse"] * V_CONC / 1000
    saved = (
        m_na_t * (EF_LIMESTONE * 1000 + d_na * EF_TRUCK_RT)
        + m_in_t * d_lf * EF_TRUCK_RT
    )
    added = (
        m_in_t * (crush_ef(crush_mj) + d_cp * EF_TRUCK_RT)
        + m_rca_t * d_rca * EF_TRUCK_RT
        + extra_cement * r * V_CONC * EF_CEMENT
    )
    return added - saved, {
        "m_rca_t": m_rca_t,
        "m_in_t": m_in_t,
        "m_na_t": m_na_t,
        "saved": saved,
        "added": added,
    }


def water_balance(r, compensate=1.0):
    m_rca = r * MIX["coarse"] * (SG_RCA / SG_NA)
    m_na = (1 - r) * MIX["coarse"]
    extra = m_rca * ABS_RCA + m_na * ABS_NA - MIX["coarse"] * ABS_NA
    wc_base = MIX["water"] / MIX["cement"]
    wc_eff = (MIX["water"] - extra * (1 - compensate)) / MIX["cement"]
    return extra, wc_base, wc_eff


def strength_ratio(r):
    return 1 - 0.06 * r


if __name__ == "__main__":
    print(
        f"M_house={M_HOUSE} kg, concrete volume={V_CONC:.1f} m3, "
        f"coarse agg={MIX['coarse'] * V_CONC / 1000:.1f} t"
    )
    print(
        f"truck round-trip EF={EF_TRUCK_RT:.4f} kgCO2e/tkm, crushing={crush_ef():.2f} kgCO2e/t"
    )

    print("\nValidation: r=0 baseline (paper whole-house 100% recycling)")
    for X in (1, 1.8):
        print(f"  X={X}: MCI={mci_house(0, X, E_F=1)[0]:.3f}")

    print("\nMCI vs r (X=1 / X=1.8), E_F=0.75 (fines lost) | E_F=1 (fines used)")
    for r in (0, 0.2, 0.5, 1.0):
        a = mci_house(r, 1, 0.75)[0]
        b = mci_house(r, 1.8, 0.75)[0]
        c = mci_house(r, 1, 1)[0]
        print(
            f"  r={r:.0%}: {a:.3f} / {b:.3f} | {c:.3f}   RCA={rca_mass(r) / 1000:.1f} t  "
            f"strength={strength_ratio(r):.2f}"
        )

    print(
        "\nWater balance per m3 (r, extra water needed, w/c base, w/c_eff if NOT compensated)"
    )
    for r in (0.2, 0.5, 1.0):
        extra, wc_base, wc_eff = water_balance(r, 0)
        print(f"  r={r:.0%}: +{extra:.1f} kg/m3, {wc_base:.3f} -> {wc_eff:.3f}")

    print("\nCO2 per house, r=100%, equal distances d (all legs), no extra cement")
    for d in (0, 15, 30, 50):
        dc, _ = co2_delta(1, d, d, d, d)
        print(f"  d={d} km: delta={dc:+.0f} kgCO2e")

    dc, info = co2_delta(1, 0, 0, 0, 0)
    print(
        f"\nProduction-only effect r=100%: {dc:+.1f} kgCO2e ({dc / info['m_rca_t']:+.2f} per t RCA)"
    )
    for ec in (22, 40):
        dc, _ = co2_delta(1, 0, 0, 0, 0, ec)
        print(f"  with +{ec} kg cement/m3: {dc:+.0f} kgCO2e")

    print(
        "\nBreak-even extra cement (kg/m3) if RCA route is shorter than NA+landfill route by D km total:"
    )
    for D in (0, 10, 20, 50):
        dc, _ = co2_delta(1, D, 0, 0, 0)
        print(f"  D={D}: {-dc / (V_CONC * EF_CEMENT):.1f} kg/m3")
