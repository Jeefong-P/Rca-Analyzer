"""Closed-loop RCA model for a Thai standard concrete house.
Every constant carries its source. Scenario variables are function arguments."""
import numpy as np

# ---- House inventory, Tanthanawiwat et al. 2024 Fig.3 (kg) ----
HOUSE = {"concrete":129226,"block":14560,"steel":9626,"tile":5129,
         "glass":462,"gypsum":109,"wood":84,"al":74}
M_HOUSE = sum(HOUSE.values())                      # 159,270 kg
# 100%-recycling EoL routes, Tanthanawiwat Fig.3 / Table 3
EOL = {"concrete":("R",1.0),"block":("R",1.0),"steel":("R",1.0),"tile":("U",1.0),
       "glass":("U",1.0),"al":("U",1.0),"gypsum":("L",0),"wood":("L",0)}

# ---- Thai mix by mass, Tangchirapat et al. 2008 (kg/m3) ----
MIX = {"cement":380,"coarse":1006,"sand":800,"water":191}
RHO_C = sum(MIX.values())                           # 2377 kg/m3
SG_NA, SG_RCA = 2.67, 2.45                          # Tangchirapat 2008
ABS_NA, ABS_RCA = 0.0046, 0.0561                    # Tangchirapat 2008
V_CONC = HOUSE["concrete"]/RHO_C                    # m3 of concrete in house

# ---- Emission factors ----
EF_CEMENT = 0.788      # kgCO2/kg, Tangthieng 2017 (727 direct + 60.5 elec, 2001-2014 avg)
EF_LIMESTONE = 0.0025  # kgCO2e/kg, TGO item 616 (Ecoinvent 2.2)
EF_TRUCK_FULL = 0.0489 # kgCO2e/tkm, TGO item 133 (10-wheel open, 16 t, 100% load)
EF_TRUCK_EMPTY = 0.6053# kgCO2e/km,  TGO item 130 (same truck, empty)
PAYLOAD = 16.0         # t, TGO item 130/133 description
EF_ELEC = 0.5562       # kgCO2e/kWh, TGO 2022-2024 CFP
CRUSH_MJ_PER_T = 8.8   # MJ/t advanced recycling, Tanthanawiwat 2024 citing Di Maria 2018
EF_TRUCK_RT = EF_TRUCK_FULL + EF_TRUCK_EMPTY/PAYLOAD  # loaded out, empty back, per tkm
EF_CRUSH = CRUSH_MJ_PER_T/3.6*EF_ELEC                  # kgCO2e per t input (assumes electric drive)
YIELD_COARSE = 0.75    # Muller 2021 (>2 mm share)

def mci_house(r, X=1.0, E_F=YIELD_COARSE, C_R_conc=1.0, E_C=1.0):
    """Whole-house MCI, EMF eqs 2.15-2.21. r = coarse-aggregate replacement (volume basis)."""
    m_rca = r*MIX["coarse"]*(SG_RCA/SG_NA)*V_CONC      # kg RCA in new house
    V=W=dW=0.0
    for k,m in HOUSE.items():
        FR = m_rca/m if k=="concrete" else 0.0
        route,frac = EOL[k]
        CR = C_R_conc if k=="concrete" else (frac if route=="R" else 0)
        CU = frac if route=="U" else 0
        v = m*(1-FR); w0 = m*(1-CR-CU)
        wc = m*(1-E_C)*CR; wf = m*(1-E_F)*FR/E_F
        V += v; W += w0+(wf+wc)/2; dW += (wf-wc)/2
    LFI = (V+W)/(2*M_HOUSE+dW)
    return max(0,1-LFI*0.9/X), LFI, m_rca

def co2_delta(r, d_na, d_cp, d_rca, d_lf, extra_cement=0.0):
    """Change in kgCO2e for the whole house vs baseline (natural aggregate, waste landfilled).
    Negative = saving. Distances in km (one way)."""
    m_rca_t = r*MIX["coarse"]*(SG_RCA/SG_NA)*V_CONC/1000
    m_in_t  = m_rca_t/YIELD_COARSE          # crushed concrete needed
    m_na_t  = r*MIX["coarse"]*V_CONC/1000   # natural coarse avoided
    saved = m_na_t*(EF_LIMESTONE*1000 + d_na*EF_TRUCK_RT) + m_in_t*d_lf*EF_TRUCK_RT
    added = (m_in_t*(EF_CRUSH + d_cp*EF_TRUCK_RT) + m_rca_t*d_rca*EF_TRUCK_RT
             + extra_cement*V_CONC*EF_CEMENT*(r>0))
    return added-saved, dict(m_rca_t=m_rca_t,m_in_t=m_in_t,m_na_t=m_na_t,saved=saved,added=added)

def water_balance(r, compensate=1.0):
    """Extra mixing water (kg/m3) to keep effective w/c, and effective w/c if not compensated."""
    m_rca = r*MIX["coarse"]*(SG_RCA/SG_NA); m_na=(1-r)*MIX["coarse"]
    absorbed_extra = m_rca*ABS_RCA + m_na*ABS_NA - MIX["coarse"]*ABS_NA
    w_eff_base = MIX["water"]/MIX["cement"]
    w_eff_uncomp = (MIX["water"]-absorbed_extra*(1-compensate))/MIX["cement"]
    return absorbed_extra, w_eff_base, w_eff_uncomp

def strength_ratio(r):
    """Coarse-only RCA: linear between Tangchirapat 2008 points (0%:1.00, 100%:0.94). Interpolation is an assumption."""
    return 1-0.06*r

if __name__=="__main__":
    print(f"M_house={M_HOUSE} kg, concrete volume={V_CONC:.1f} m3, coarse agg={MIX['coarse']*V_CONC/1000:.1f} t")
    print(f"truck round-trip EF={EF_TRUCK_RT:.4f} kgCO2e/tkm, crushing={EF_CRUSH:.2f} kgCO2e/t")
    print("\nValidation: r=0 baseline (paper whole-house 100% recycling)")
    for X in (1,1.8): print(f"  X={X}: MCI={mci_house(0,X,E_F=1)[0]:.3f}")
    print("\nMCI vs r (X=1 / X=1.8), E_F=0.75 (fines lost) | E_F=1 (fines used)")
    for r in (0,0.2,0.5,1.0):
        a=mci_house(r,1,0.75)[0]; b=mci_house(r,1.8,0.75)[0]; c=mci_house(r,1,1)[0]; m=mci_house(r)[2]
        print(f"  r={r:.0%}: {a:.3f} / {b:.3f} | {c:.3f}   RCA={m/1000:.1f} t  strength={strength_ratio(r):.2f}")
    print("\nWater balance per m3 (r, extra water needed, w/c base, w/c_eff if NOT compensated)")
    for r in (0.2,0.5,1.0):
        e,b,u=water_balance(r,0); print(f"  r={r:.0%}: +{e:.1f} kg/m3, {b:.3f} -> {u:.3f}")
    print("\nCO2 per house, r=100%, equal distances d (all legs), no extra cement")
    for d in (0,15,30,50):
        dc,_=co2_delta(1,d,d,d,d); print(f"  d={d} km: delta={dc:+.0f} kgCO2e")
    # per tonne of RCA, everything else zero: production-only effect
    dc,info=co2_delta(1,0,0,0,0); print(f"\nProduction-only effect r=100%: {dc:+.1f} kgCO2e ({dc/info['m_rca_t']:+.2f} per t RCA)")
    for ec in (22,40):
        dc,_=co2_delta(1,0,0,0,0,ec); print(f"  with +{ec} kg cement/m3: {dc:+.0f} kgCO2e")
    # break-even extra cement given distance advantage
    print("\nBreak-even extra cement (kg/m3) if RCA route is shorter than NA+landfill route by D km total:")
    for D in (0,10,20,50):
        dc,info=co2_delta(1,D,0,0,0)
        print(f"  D={D}: {(-dc)/(V_CONC*EF_CEMENT):.1f} kg/m3")
