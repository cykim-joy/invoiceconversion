"""
db_manager.py
─────────────
품목코드 DB (CSV) 의 로드 / 저장 / 조회를 담당합니다.

DB 컬럼
  바코드 | 영문품목명 | 한글품목명 | 어드민코드 | 비고
"""

from pathlib import Path
import pandas as pd

# ─── 파일 경로 ────────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent.parent          # app.py 와 같은 레벨
DB_PATH   = _BASE_DIR / "data" / "품목코드DB.csv"

_COLUMNS = ["바코드", "영문품목명", "한글품목명", "어드민코드", "비고"]


# ─── 로드 ─────────────────────────────────────────────────────────────────────
def load_product_db() -> pd.DataFrame:
    """DB CSV를 로드. 파일이 없으면 빈 DataFrame 반환."""
    if DB_PATH.exists():
        try:
            df = pd.read_csv(DB_PATH, dtype=str).fillna("")
            # 없는 컬럼 보완
            for col in _COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            return df[_COLUMNS]
        except Exception:
            pass

    return pd.DataFrame(columns=_COLUMNS)


# ─── 저장 ─────────────────────────────────────────────────────────────────────
def save_product_db(df: pd.DataFrame) -> None:
    """DB를 CSV로 저장."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 없는 컬럼 보완
    for col in _COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df[_COLUMNS].to_csv(DB_PATH, index=False, encoding="utf-8-sig")


# ─── 조회 ─────────────────────────────────────────────────────────────────────
def lookup_product(db: pd.DataFrame, eng_name: str = "", barcode: str = "") -> dict:
    """
    바코드(우선) 또는 영문품목명으로 DB를 조회합니다.

    Returns
    -------
    dict with English keys matching the product dict:
        {
          "korean_name": str,
          "admin_code":  str,
          "matched":     bool,
        }
    """
    if db.empty:
        return {"korean_name": "", "admin_code": "", "matched": False}

    row = None

    # 1순위: 바코드 일치
    if barcode:
        mask = db["바코드"].str.strip() == barcode.strip()
        if mask.any():
            row = db[mask].iloc[0]

    # 2순위: 영문품목명 일치 (대소문자 무시)
    if row is None and eng_name:
        mask = db["영문품목명"].str.strip().str.lower() == eng_name.strip().lower()
        if mask.any():
            row = db[mask].iloc[0]

    # 3순위: 영문품목명 부분 포함
    if row is None and eng_name:
        mask = db["영문품목명"].str.contains(eng_name.strip(), case=False, na=False, regex=False)
        if mask.any():
            row = db[mask].iloc[0]

    if row is not None:
        return {
            "korean_name": str(row.get("한글품목명", "")),
            "admin_code":  str(row.get("어드민코드", "")),
            "matched":     True,
        }

    return {"korean_name": "", "admin_code": "", "matched": False}
