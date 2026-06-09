# =============================================================
# TEAMPULSE PROCESSOR
# Reads Base_1, Base_2, Base_3 — processes metrics — injects
# into teampulse_dashboard.html — saves teampulse_output.html
# =============================================================

import pandas as pd
import numpy as np
import json
import re
from datetime import datetime

# =============================================================
# 1. CONFIGURATION
# =============================================================
BASE_DIR       = r"C:\Users\enzop\Downloads"
BASE_1_PATH    = BASE_DIR + r"\Base_1.csv"
BASE_2_PATH    = BASE_DIR + r"\Base_2.csv"
BASE_3_PATH    = BASE_DIR + r"\Base_3.csv"
HTML_BASE      = BASE_DIR + r"\teampulse_dashboard.html"
HTML_OUTPUT    = BASE_DIR + r"\teampulse_output.html"

# =============================================================
# 2. TEAM MEMBERS
# =============================================================
TEAM_A = [f"Name {i}" for i in range(1, 10)]   # Names 1-9
TEAM_B = [f"Name {i}" for i in range(10, 15)]  # Names 10-14

ALL_MEMBERS = TEAM_A + TEAM_B

TEAMS_DEF = {
    "Team A": TEAM_A,
    "Team B": TEAM_B,
}

DEFAULT_GRADIENTS = [
    "linear-gradient(135deg,#2551E3,#8069B4)",
    "linear-gradient(135deg,#FF3C28,#F5A623)",
    "linear-gradient(135deg,#108981,#06B6D4)",
    "linear-gradient(135deg,#885CF6,#2551E3)",
    "linear-gradient(135deg,#F5A623,#8069B4)",
    "linear-gradient(135deg,#0EA5E9,#2551E3)",
    "linear-gradient(135deg,#14BB86,#108981)",
    "linear-gradient(135deg,#FF3C28,#885CF6)",
    "linear-gradient(135deg,#4F9731,#06B6D4)",
    "linear-gradient(135deg,#8069B4,#FF3C28)",
    "linear-gradient(135deg,#06B6D4,#885CF6)",
    "linear-gradient(135deg,#F5A623,#FF3C28)",
    "linear-gradient(135deg,#2551E3,#14BB86)",
    "linear-gradient(135deg,#885CF6,#F5A623)",
]

# =============================================================
# 3. HELPER FUNCTIONS
# =============================================================
def safe_float(val, default=0.0):
    try:
        v = float(val)
        return v if not np.isnan(v) else default
    except:
        return default

def safe_round(val, decimals=2):
    try:
        return round(float(val), decimals)
    except:
        return 0.0

def month_label(period):
    """Convert a period (datetime or string) to 'Mon 'YY' format."""
    months = ['Jan','Feb','Mar','Apr','May','Jun',
              'Jul','Aug','Sep','Oct','Nov','Dec']
    if isinstance(period, str):
        period = pd.to_datetime(period)
    return f"{months[period.month - 1]} '{str(period.year)[2:]}"

def get_initials(name):
    parts = name.strip().split()
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()

# =============================================================
# 4. LOAD & CLEAN DATA
# =============================================================
def load_and_clean():
    print("Loading bases...")

    # Base 1
    b1 = pd.read_csv(BASE_1_PATH)
    b1.columns = [c.strip().lower().replace(" ", "_") for c in b1.columns]
    b1["capture_date"] = pd.to_datetime(b1["capture_date"], errors="coerce")
    b1["status"] = b1["status"].astype(str).str.strip().str.upper().isin(["TRUE", "1", "YES"])
    b1["sla"] = pd.to_numeric(b1["sla"], errors="coerce")
    b1["score"] = pd.to_numeric(b1["score"], errors="coerce")
    b1["maker"] = b1["maker"].astype(str).str.strip()
    b1["checker"] = b1["checker"].astype(str).str.strip()
    b1["team"] = b1["team"].astype(str).str.strip()
    b1["type"] = b1["type"].astype(str).str.strip()
    b1["month"] = b1["capture_date"].apply(month_label)

    # Base 3
    b3 = pd.read_csv(BASE_3_PATH)
    b3.columns = [c.strip().lower().replace(" ", "_") for c in b3.columns]
    b3.rename(columns={
        b3.columns[0]: "client_id",
        b3.columns[1]: "responsible_team"
    }, inplace=True)
    b3["client_id"] = b3["client_id"].astype(str).str.strip()
    b3["responsible_team"] = b3["responsible_team"].astype(str).str.strip()

    # Base 2
    b2 = pd.read_csv(BASE_2_PATH)
    b2.columns = [c.strip().lower().replace(" ", "_") for c in b2.columns]
    b2["client_id"] = b2["client_id"].astype(str).str.strip()
    b2["score"] = pd.to_numeric(b2["score"], errors="coerce")
    b2["transaction_version"] = pd.to_numeric(b2["transaction_version"], errors="coerce")
    b2["maker"] = b2["maker"].astype(str).str.strip()
    b2["checker"] = b2["checker"].astype(str).str.strip()
    b2["agreement_type"] = b2["agreement_type"].astype(str).str.strip()
    b2["latest_status"] = b2["latest_status"].astype(str).str.strip()
    b2["first_score_completed_date"] = pd.to_datetime(
        b2["first_score_completed_date"], errors="coerce"
    )

    # Merge Base 2 with Base 3 to get responsible_team
    b2 = b2.merge(b3[["client_id", "responsible_team"]], on="client_id", how="left")
    b2["month"] = b2["first_score_completed_date"].apply(
        lambda x: month_label(x) if pd.notna(x) else None
    )

    print(f"  Base 1: {len(b1)} rows")
    print(f"  Base 2: {len(b2)} rows")
    print(f"  Base 3: {len(b3)} rows")

    return b1, b2, b3

# =============================================================
# 5. EXTRACT METRICS
# =============================================================
def extract_ubts(b1):
    """
    Disbursements (UBTs):
    - status == True
    - unique by transaction_number
    - Single Deal = UBT, Master Deal = Parent
    """
    df = b1[b1["status"] == True].drop_duplicates(subset=["transaction_number"])
    return df

def extract_live(b2):
    """New Deals: agreement_type=New Deal, status=Score Completed, version=1"""
    df = b2[
        (b2["agreement_type"] == "New Deal") &
        (b2["latest_status"] == "Score Completed") &
        (b2["transaction_version"] == 1)
    ].drop_duplicates(subset=["original_deal_id"])
    return df

def extract_post(b2):
    """Reviews: agreement_type=Review, status=Score Completed, version!=1"""
    df = b2[
        (b2["agreement_type"] == "Review") &
        (b2["latest_status"] == "Score Completed") &
        (b2["transaction_version"] != 1)
    ].drop_duplicates(subset=["original_deal_id"])
    return df

def extract_amend(b2):
    """Amendments: agreement_type=Amendment, status=Score Completed, version!=1"""
    df = b2[
        (b2["agreement_type"] == "Amendment") &
        (b2["latest_status"] == "Score Completed") &
        (b2["transaction_version"] != 1)
    ].drop_duplicates(subset=["original_deal_id"])
    return df

# =============================================================
# 6. BUILD ALL_MONTHS
# =============================================================
def build_all_months(b1, b2):
    """All months from Jan 2025 to current month, in order."""
    months_short = ['Jan','Feb','Mar','Apr','May','Jun',
                    'Jul','Aug','Sep','Oct','Nov','Dec']
    now = datetime.now()
    all_months = []
    for y in range(2025, now.year + 1):
        max_m = now.month if y == now.year else 12
        for m in range(1, max_m + 1):
            all_months.append(f"{months_short[m-1]} '{str(y)[2:]}")
    return all_months

# =============================================================
# 7. CALC MEMBER METRICS
# =============================================================
def calc_member_ubts(name, ubts_df, all_months):
    """Build makerRows and checkerRows for UBTs."""
    is_single = ubts_df["type"].str.lower().str.contains("single")

    maker_df   = ubts_df[ubts_df["maker"] == name]
    checker_df = ubts_df[ubts_df["checker"] == name]

    maker_rows = []
    for mo in all_months:
        mdf = maker_df[maker_df["month"] == mo]
        cnt    = int(mdf[is_single[mdf.index]].shape[0]) if len(mdf) > 0 else 0
        parent = int((~is_single[mdf.index]).sum()) if len(mdf) > 0 else 0
        sla_vals = mdf["sla"].dropna()
        sla = safe_round(sla_vals.mean(), 2) if len(sla_vals) > 0 else None
        maker_rows.append({
            "m": mo,
            "cnt": cnt,
            "parent": parent,
            "sla": str(sla) if sla is not None else None,
            "qc": 0
        })

    checker_rows = []
    for mo in all_months:
        cdf = checker_df[checker_df["month"] == mo]
        cnt    = int(cdf[is_single[cdf.index]].shape[0]) if len(cdf) > 0 else 0
        parent = int((~is_single[cdf.index]).sum()) if len(cdf) > 0 else 0
        qc_vals = cdf["score"].dropna()
        qc = safe_round(qc_vals.mean(), 1) if len(qc_vals) > 0 else None
        checker_rows.append({
            "m": mo,
            "cnt": cnt,
            "parent": parent,
            "sla": 0,
            "qc": float(qc) if qc is not None else 0
        })

    return maker_rows, checker_rows

def calc_member_metric(name, df, all_months, role_col_maker="maker", role_col_checker="checker"):
    """Build makerCounts, checkerCounts, makerQC, checkerQC arrays."""
    maker_counts   = []
    checker_counts = []
    maker_qc       = []
    checker_qc     = []

    for mo in all_months:
        mdf = df[(df[role_col_maker] == name) & (df["month"] == mo)]
        cdf = df[(df[role_col_checker] == name) & (df["month"] == mo)]

        maker_counts.append(int(len(mdf)))
        checker_counts.append(int(len(cdf)))

        m_qc = mdf["score"].dropna()
        c_qc = cdf["score"].dropna()
        maker_qc.append(float(safe_round(m_qc.mean(), 1)) if len(m_qc) > 0 else 0)
        checker_qc.append(float(safe_round(c_qc.mean(), 1)) if len(c_qc) > 0 else 0)

    return maker_counts, checker_counts, maker_qc, checker_qc

# =============================================================
# 8. BUILD MEMBERS_DATA & TEAMS
# =============================================================
def build_data(b1, b2):
    disbursements = extract_ubts(b1)
    live  = extract_live(b2)
    post  = extract_post(b2)
    amend = extract_amend(b2)

    all_months = build_all_months(b1, b2)

    members_data = {}
    teams        = {}
    global_idx   = 0

    for team_name, members in TEAMS_DEF.items():
        teams[team_name] = {"name": team_name, "members": []}

        for name in members:
            mid = f"m{global_idx}"

            # UBTs
            maker_rows, checker_rows = calc_member_ubts(name, disbursements, all_months)

            # Live / Post / Amend
            lm, lc, lmq, lcq = calc_member_metric(name, live,  all_months)
            pm, pc, pmq, pcq = calc_member_metric(name, post,  all_months)
            am, ac, amq, acq = calc_member_metric(name, amend, all_months)

            member = {
                "id":        mid,
                "name":      name,
                "initials":  get_initials(name),
                "team":      team_name,
                "role":      "Analyst",
                "gradient":  DEFAULT_GRADIENTS[global_idx % len(DEFAULT_GRADIENTS)],
                "Disbursements": {
                    "makerRows":   maker_rows,
                    "checkerRows": checker_rows,
                },
                "live": {
                    "makerCounts":   lm,
                    "checkerCounts": lc,
                    "makerQC":       lmq,
                    "checkerQC":     lcq,
                },
                "post": {
                    "makerCounts":   pm,
                    "checkerCounts": pc,
                    "makerQC":       pmq,
                    "checkerQC":     pcq,
                },
                "amend": {
                    "makerCounts":   am,
                    "checkerCounts": ac,
                    "makerQC":       amq,
                    "checkerQC":     acq,
                },
            }

            members_data[mid] = member
            teams[team_name]["members"].append(member)
            global_idx += 1

    # TM = all members
    teams["tm"] = {"name": "ALL", "members": list(members_data.values())}

    return all_months, members_data, teams

# =============================================================
# 9. INJECT INTO HTML & SAVE
# =============================================================
def inject_and_save(all_months, members_data, teams):
    print("Reading HTML template...")
    with open(HTML_BASE, "r", encoding="utf-8") as f:
        html = f.read()

    all_months_json  = json.dumps(all_months,  ensure_ascii=False)
    members_data_json = json.dumps(members_data, ensure_ascii=False)
    teams_json       = json.dumps(teams,        ensure_ascii=False)

    html = html.replace("/*%%ALL_MONTHS%%*/[]",    f"/*%%ALL_MONTHS%%*/{all_months_json}")
    html = html.replace("/*%%MEMBERS_DATA%%*/{}",  f"/*%%MEMBERS_DATA%%*/{members_data_json}")
    html = html.replace("/*%%TEAMS%%*/{}",         f"/*%%TEAMS%%*/{teams_json}")
    html = html.replace("/*%%TEAM_UNIQUE_TOTALS%%*/{}","/*%%TEAM_UNIQUE_TOTALS%%*/{}")

    with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Output saved: {HTML_OUTPUT}")

# =============================================================
# 10. MAIN
# =============================================================
def main():
    print("=" * 50)
    print("  TEAMPULSE PROCESSOR")
    print("=" * 50)

    b1, b2, b3 = load_and_clean()

    print("\nBuilding metrics...")
    all_months, members_data, teams = build_data(b1, b2)

    print(f"  Months: {len(all_months)}")
    print(f"  Members: {len(members_data)}")
    print(f"  Teams: {list(teams.keys())}")

    print("\nInjecting into HTML...")
    inject_and_save(all_months, members_data, teams)

    print("\nDone! Open teampulse_output.html to view the dashboard.")
    print("=" * 50)

if __name__ == "__main__":
    main()
